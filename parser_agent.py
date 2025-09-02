import os
import ast
from flask import Flask, request, make_response

app = Flask(__name__)

@app.route('/parse', methods=['POST']) # Parsing python code
def parse():
    try:
        code = request.json.get('code', '')
        result = generate_mermaid_flowchart(code)
        response = make_response(result, 200)
        response.headers['Content-Type'] = 'text/plain'
        return response
    except Exception as e:
        return make_response(f"Error: {str(e)}", 500)

def parse_code(code): # For the flowchart
    tree = ast.parse(code)
    parsed_lines = []
    branching_map = {}
    counter = 0
    node_id_map = {}

    def visit(node, parent_id=None):
        nonlocal counter

        label = ""
        shape = ""

        if isinstance(node, ast.FunctionDef):
            args = [arg.arg for arg in node.args.args]
            label = f"def {node.name}({', '.join(args)})"
            shape = "subproc"

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

                for yes_node in node.body:
                    visit(yes_node)
                    yes_ids.append(node_id_map[id(yes_node)])

                for no_node in node.orelse:
                    visit(no_node)
                    no_ids.append(node_id_map[id(no_node)])

                branching_map[node_id] = {
                    "yes": yes_ids,
                    "no": no_ids
                }

                # Create merge node
                merge_id = f"N{counter}"
                parsed_lines.append({
                    "id": merge_id,
                    "line": "Merge",
                    "shape": "circle"
                })
                counter += 1

                # Link terminal nodes of both branches to merge
                for tid in yes_ids[-1:]:
                    branching_map.setdefault(tid, {})
                    branching_map[tid]["next"] = merge_id

                for tid in no_ids[-1:]:
                    branching_map.setdefault(tid, {})
                    branching_map[tid]["next"] = merge_id

                branching_map[node_id]["merge"] = merge_id
                node_id_map[id(merge_id)] = merge_id

                return  # Skip default child visit for If

        for child in ast.iter_child_nodes(node):
            visit(child)

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
    visited = set()

    for i in range(len(parsed_lines) - 1):
        src = parsed_lines[i]["id"]
        dst = parsed_lines[i + 1]["id"]

        if src in branching_map:
            if "yes" in branching_map[src]:
                for yt in branching_map[src]["yes"]:
                    edges.append(f"{src} -->|Yes| {yt}")
            if "no" in branching_map[src]:
                for nt in branching_map[src]["no"]:
                    edges.append(f"{src} -->|No| {nt}")
            if "merge" in branching_map[src]:
                merge_id = branching_map[src]["merge"]
                visited.add(merge_id)
        elif src not in visited:
            edges.append(f"{src} --> {dst}")

    # Add 'next' links from terminal nodes to merge
    for src, targets in branching_map.items():
        if "next" in targets:
            edges.append(f"{src} --> {targets['next']}")

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
