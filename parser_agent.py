import os
import ast
import traceback
from flask import Flask, request, make_response

app = Flask(__name__)

@app.route('/parse', methods=['POST'])
def parse():
    try:
        code = request.json.get('code', '')
        result = generate_mermaid_flowchart(code)
        response = make_response(result, 200)
        response.headers['Content-Type'] = 'text/plain'
        return response
    except Exception:
        error_msg = traceback.format_exc()
        return make_response(f"Error:\n{error_msg}", 500)

def parse_code(code):
    tree = ast.parse(code)
    parsed_lines = []
    branching_map = {}
    node_id_map = {}
    visited_nodes = set()
    seen_labels = set()
    counter = 0

    def add_node(label, shape):
        nonlocal counter
        if not label.strip() or label in seen_labels:
            return None
        seen_labels.add(label)
        node_id = f"N{counter}"
        parsed_lines.append({"id": node_id, "line": label, "shape": shape})
        counter += 1
        return node_id

    def link_sequential_flow(body):
        for i in range(len(body) - 1):
            src = node_id_map.get(id(body[i]))
            dst = node_id_map.get(id(body[i + 1]))
            if src and dst:
                branching_map.setdefault(src, {})["next"] = dst

    def visit(node, parent_body=None):
        if id(node) in visited_nodes:
            return
        visited_nodes.add(id(node))

        if isinstance(node, ast.Module):
            for child in node.body:
                visit(child, node.body)
            return

        label, shape = "", ""

        if isinstance(node, ast.FunctionDef):
            args = [arg.arg for arg in node.args.args]
            label = f"def {node.name}({', '.join(args)})"
            shape = "subproc"
            node_id = add_node(label, shape)
            if node_id:
                node_id_map[id(node)] = node_id
                for i, child in enumerate(node.body):
                    visit(child, node.body)
                    child_id = node_id_map.get(id(child))
                    if i == 0 and child_id:
                        branching_map[node_id] = {"next": child_id}
                link_sequential_flow(node.body)
            return

        elif isinstance(node, ast.If):
            label = f"if {ast.unparse(node.test)}"
            shape = "diamond"

        elif isinstance(node, ast.For):
            label = f"for {ast.unparse(node.target)} in {ast.unparse(node.iter)}"
            shape = "hex"

        elif isinstance(node, ast.While):
            label = f"while {ast.unparse(node.test)}"
            shape = "hex"

        elif isinstance(node, ast.Continue):
            label = "continue"
            shape = "dbl-circ"

        elif isinstance(node, ast.Return):
            label = f"return {ast.unparse(node.value)}" if node.value else "return"
            shape = "dbl-circ"

        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func_name = getattr(node.value.func, 'id', ast.unparse(node.value.func))
            args = [ast.unparse(arg) for arg in node.value.args]
            label = f"{func_name}({', '.join(args)})"
            if func_name in ["print", "input"]:
                shape = "in-out"

        elif isinstance(node, ast.Assign):
            targets = [ast.unparse(t) for t in node.targets]
            value = ast.unparse(node.value)
            label = f"{' = '.join(targets)} = {value}"
            shape = "rect"

        node_id = add_node(label, shape)
        if node_id:
            node_id_map[id(node)] = node_id

        if isinstance(node, ast.If):
            yes_ids, no_ids = [], []

            for yes_node in node.body:
                visit(yes_node, node.body)
                yes_id = node_id_map.get(id(yes_node))
                if yes_id:
                    yes_ids.append(yes_id)
            link_sequential_flow(node.body)

            for no_node in node.orelse:
                visit(no_node, node.orelse)
                no_id = node_id_map.get(id(no_node))
                if no_id:
                    no_ids.append(no_id)
            link_sequential_flow(node.orelse)

            branching_map[node_id] = {"yes": yes_ids, "no": no_ids}

        elif isinstance(node, (ast.For, ast.While)):
            for loop_node in node.body:
                visit(loop_node, node.body)
            link_sequential_flow(node.body)
            last_id = node_id_map.get(id(node.body[-1]))
            if last_id and node_id:
                branching_map.setdefault(last_id, {})["next"] = node_id

        for child in ast.iter_child_nodes(node):
            visit(child, parent_body)

    visit(tree)
    return parsed_lines, branching_map

def build_mermaid_nodes(parsed_lines):
    nodes = []
    annotations = []
    for item in parsed_lines:
        nodes.append(f'{item["id"]}["{item["line"]}"]')
        annotations.append(f'{item["id"]}@{{ shape: {item["shape"]} }}')
    return nodes, annotations

def build_mermaid_edges(parsed_lines, branching_map):
    edges = []
    linked_to_end = set()

    for src, targets in branching_map.items():
        if "yes" in targets:
            for yt in targets["yes"]:
                edges.append(f"{src} -->|Yes| {yt}")
        if "no" in targets:
            for nt in targets["no"]:
                edges.append(f"{src} -->|No| {nt}")
        if "next" in targets:
            edges.append(f"{src} --> {targets['next']}")

    for item in parsed_lines:
        if item["line"].startswith("return") and all(f"{item['id']} -->" not in e for e in edges):
            if item["id"] not in linked_to_end:
                edges.append(f'{item["id"]} --> End')
                linked_to_end.add(item["id"])

    return edges

def generate_mermaid_flowchart(code):
    parsed, branching_map = parse_code(code)
    if not parsed:
        return "flowchart TD\nStart --> End\nStart([\"Start\"])\nEnd([\"End\"])"

    nodes, annotations = build_mermaid_nodes(parsed)
    edges = build_mermaid_edges(parsed, branching_map)

    nodes.insert(0, 'Start(["Start"])')
    edges.insert(0, f'Start --> {parsed[0]["id"]}')
    nodes.append('End(["End"])')

    last_id = parsed[-1]["id"]
    if f"{last_id} --> End" not in edges:
        edges.append(f"{last_id} --> End")

    return "flowchart TD\n" + "\n".join(nodes + edges) + "\n" + "\n".join(annotations)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)