import os
import ast
from flask import Flask, request, make_response

app = Flask(__name__)

@app.route('/parse', methods=['POST'])  # Parsing python code
def parse():
    try:
        code = request.json.get('code', '')
        result = generate_mermaid_flowchart(code)
        response = make_response(result, 200)
        response.headers['Content-Type'] = 'text/plain'
        return response
    except Exception as e:
        return make_response(f"Error: {str(e)}", 500)

def parse_code(code):  # For the flowchart
    tree = ast.parse(code)
    parsed_lines = []
    branching_map = {}
    counter = 0
    node_id_map = {}
    visited_nodes = set()

    def visit(node, parent_body=None):
        nonlocal counter

        if id(node) in visited_nodes:
            return
        visited_nodes.add(id(node))

        label = ""
        shape = ""

        if isinstance(node, ast.FunctionDef):
            args = [arg.arg for arg in node.args.args]
            label = f"def {node.name}({', '.join(args)})"
            shape = "subproc"
            node_id = f"N{counter}"
            parsed_lines.append({
                "id": node_id,
                "line": label,
                "shape": shape
            })
            node_id_map[id(node)] = node_id
            counter += 1

            parent_body = node.body
            if parent_body:
                visit(parent_body[0], parent_body)
                first_child_id = node_id_map[id(parent_body[0])]
                branching_map[node_id] = {"next": first_child_id}
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

        elif isinstance(node, ast.Return):
            label = f"return {ast.unparse(node.value)}"
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

        if label and shape:
            node_id = f"N{counter}"
            parsed_lines.append({
                "id": node_id,
                "line": label,
                "shape": shape
            })
            node_id_map[id(node)] = node_id
            counter += 1

            if isinstance(node, ast.If):
                yes_ids = []
                no_ids = []
                terminal_ids = []

                for yes_node in node.body:
                    visit(yes_node, node.body)
                    yes_ids.append(node_id_map[id(yes_node)])
                if yes_ids:
                    terminal_ids.append(yes_ids[-1])

                def visit_orelse_block(orelse):
                    for sub_node in orelse:
                        if isinstance(sub_node, ast.If):
                            visit(sub_node, parent_body)
                            sub_id = node_id_map[id(sub_node)]
                            if sub_id in branching_map:
                                for branch in ["yes", "no"]:
                                    ids = branching_map[sub_id].get(branch, [])
                                    if ids:
                                        terminal_ids.append(ids[-1])
                        else:
                            visit(sub_node, parent_body)
                            no_ids.append(node_id_map[id(sub_node)])
                    if no_ids:
                        terminal_ids.append(no_ids[-1])

                visit_orelse_block(node.orelse)

                branching_map[node_id] = {
                    "yes": yes_ids,
                    "no": no_ids
                }

                if parent_body:
                    idx = next((i for i, n in enumerate(parent_body) if n is node), None)
                    if idx is not None and idx + 1 < len(parent_body):
                        next_node = parent_body[idx + 1]
                        visit(next_node, parent_body)
                        next_id = node_id_map[id(next_node)]
                        for tid in terminal_ids:
                            branching_map.setdefault(tid, {})["next"] = next_id
                return

        for child in ast.iter_child_nodes(node):
            visit(child, parent_body)

    visit(tree)
    return parsed_lines, branching_map

def build_mermaid_nodes(parsed_lines):
    mermaid_lines = []
    shape_annotations = []

    for item in parsed_lines:
        node_id = item["id"]
        label = item["line"]
        shape = item["shape"]
        mermaid_lines.append(f'{node_id}["{label}"]')
        shape_annotations.append(f'{node_id}@{{ shape: {shape} }}')

    return mermaid_lines, shape_annotations

def build_mermaid_edges(parsed_lines, branching_map):
    edges = []

    for src, targets in branching_map.items():
        if "yes" in targets:
            for yt in targets["yes"]:
                edges.append(f"{src} -->|Yes| {yt}")
        if "no" in targets:
            for nt in targets["no"]:
                edges.append(f"{src} -->|No| {nt}")
        if "next" in targets:
            edges.append(f"{src} --> {targets['next']}")

    for i in range(len(parsed_lines) - 1):
        src = parsed_lines[i]["id"]
        dst = parsed_lines[i + 1]["id"]
        if not any(src == b or src in branching_map for b in [t["id"] for t in parsed_lines]):
            edges.append(f"{src} --> {dst}")

    return edges

def generate_mermaid_flowchart(code):
    parsed, branching_map = parse_code(code)
    nodes, annotations = build_mermaid_nodes(parsed)
    edges = build_mermaid_edges(parsed, branching_map)

    nodes.insert(0, 'Start(["Start"])')
    edges.insert(0, f'Start --> {parsed[0]["id"]}')

    last_id = parsed[-1]["id"]
    nodes.append('End(["End"])')
    edges.append(f'{last_id} --> End')

    flowchart = "flowchart TD\n" + "\n".join(nodes + edges)
    annotation_block = "\n" + "\n".join(annotations)

    return flowchart + annotation_block

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)