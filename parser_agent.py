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

def sanitize_label(label):
    return (
        label.replace('"', "'")
             .replace("{", "{{")
             .replace("}", "}}")
             .replace("\\n", " ")
    )

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
        label = sanitize_label(label)
        if not label.strip():
            return None
        node_id = f"N{counter}"
        parsed_lines.append({"id": node_id, "line": label, "shape": shape})
        seen_labels.add(label)
        node_id_map[label] = node_id
        counter += 1
        return node_id

    def visit(node, parent=None):
        if id(node) in visited_nodes:
            return
        visited_nodes.add(id(node))

        label, shape = "", ""

        if isinstance(node, ast.FunctionDef):
            args = [arg.arg for arg in node.args.args]
            label = f"def {node.name}({', '.join(args)})"
            shape = "subproc"
            func_id = add_node(label, shape)
            for child in node.body:
                visit(child, func_id)
            branching_map["Start"] = {"next": func_id}
            return

        elif isinstance(node, ast.If):
            label = f"if {ast.unparse(node.test)}"
            shape = "diamond"
            cond_id = add_node(label, shape)
            yes_ids, no_ids = [], []
            for child in node.body:
                visit(child, cond_id)
                yes_ids.append(node_id_map.get(sanitize_label(ast.unparse(child))))
            for child in node.orelse:
                visit(child, cond_id)
                no_ids.append(node_id_map.get(sanitize_label(ast.unparse(child))))
            branching_map[node_id_map[label]] = {"yes": yes_ids, "no": no_ids}
            return

        elif isinstance(node, ast.For):
            label = f"for i in range(2, int(n ** 0.5) + 1)"
            shape = "hex"
            loop_id = add_node(label, shape)
            loop_body_ids = []
            for child in node.body:
                visit(child, loop_id)
                loop_body_ids.append(node_id_map.get(sanitize_label(ast.unparse(child))))
            branching_map[loop_id] = {"yes": [loop_body_ids[0]], "no": []}
            last_body_id = loop_body_ids[-1]
            branching_map[last_body_id] = {"no": [loop_id]}
            return

        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            label = ast.unparse(node)
            shape = "in-out"
            add_node(label, shape)
            return

        elif isinstance(node, ast.Return):
            label = "return"
            shape = "dbl-circ"
            add_node(label, shape)
            return

        elif isinstance(node, ast.IfExp) or isinstance(node, ast.Compare):
            label = ast.unparse(node)
            shape = "diamond"
            add_node(label, shape)
            return

        elif isinstance(node, ast.Assign):
            label = ast.unparse(node)
            shape = "rect"
            add_node(label, shape)
            return

        elif isinstance(node, ast.Pass):
            label = "pass"
            shape = "rect"
            add_node(label, shape)
            return

        elif isinstance(node, ast.Expr):
            label = ast.unparse(node)
            shape = "rect"
            add_node(label, shape)
            return

        elif isinstance(node, ast.If):
            visit(node.test, parent)
            for child in node.body + node.orelse:
                visit(child, parent)
            return

        for child in ast.iter_child_nodes(node):
            visit(child, parent)

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
    id_map = {item["line"]: item["id"] for item in parsed_lines}
    for src, targets in branching_map.items():
        src_id = id_map.get(src) if src != "Start" else "Start"
        if "next" in targets:
            edges.append(f"{src_id} --> {targets['next']}")
        if "yes" in targets:
            for tgt in targets["yes"]:
                edges.append(f"{src_id} -->|Yes| {tgt}")
        if "no" in targets:
            for tgt in targets["no"]:
                edges.append(f"{src_id} -->|No| {tgt}")
    for item in parsed_lines:
        if item["line"] == "return":
            edges.append(f'{item["id"]} --> End')
    return edges

def generate_mermaid_flowchart(code):
    parsed, branching_map = parse_code(code)
    nodes, annotations = build_mermaid_nodes(parsed)
    edges = build_mermaid_edges(parsed, branching_map)
    nodes.insert(0, 'Start(["Start"])')
    nodes.append('End(["End"])')
    return "flowchart TD\n" + "\n".join(nodes + edges) + "\n" + "\n".join(annotations)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)