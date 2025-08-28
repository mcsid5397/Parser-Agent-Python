import os
import ast
from flask import Flask, request, jsonify, make_response

app = Flask(__name__)

@app.route('/parse', methods=['POST'])
def parse():
    code = request.json.get('code', '')
    result = parse_code(code)
    response = make_response(jsonify(result), 200)
    response.headers['Content-Type'] = 'application/json'
    return response

def parse_code(code):
    tree = ast.parse(code)
    parsed_lines = []
    counter = 0

    for node in ast.walk(tree):
        label = ""
        shape = ""

        if isinstance(node, ast.FunctionDef):
            label = f"def {node.name}(...)"
            shape = "subproc"

        elif isinstance(node, ast.If):
            label = "if ..."
            shape = "diamond"

        elif isinstance(node, ast.For):
            label = "for ..."
            shape = "hex"

        elif isinstance(node, ast.While):
            label = "while ..."
            shape = "hex"

        elif isinstance(node, ast.Return):
            label = "return ..."
            shape = "dbl-circ"

        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func_name = getattr(node.value.func, 'id', '')
            if func_name in ["print", "input"]:
                label = f"{func_name}(...)"
                shape = "in-out"

        elif isinstance(node, ast.Assign):
            label = "assignment"
            shape = "rect"

        if label and shape:
            parsed_lines.append({
                "id": f"N{counter}",
                "line": label,
                "shape": shape
            })
            counter += 1

    return parsed_lines

def build_mermaid_nodes(parsed_lines):
    mermaid_lines = []
    shape_annotations = []

    for item in parsed_lines:
        node_id = item["id"]
        label = item["line"]
        shape = item["shape"]

        # Mermaid node syntax
        mermaid_lines.append(f'{node_id}["{label}"]')

        # Symbol annotation
        shape_annotations.append(f'{node_id}@{{ shape: {shape} }}')

    return mermaid_lines, shape_annotations

def build_mermaid_edges(parsed_lines):
    edges = []
    for i in range(len(parsed_lines) - 1):
        src = parsed_lines[i]["id"]
        dst = parsed_lines[i + 1]["id"]
        edges.append(f"{src} --> {dst}")
    return edges    

def generate_mermaid_flowchart(code):
    parsed = parse_code(code)
    nodes, annotations = build_mermaid_nodes(parsed)
    edges = build_mermaid_edges(parsed)

    # Add Start node and edge
    nodes.insert(0, 'Start(["Start"])')
    edges.insert(0, f'Start --> {parsed[0]["id"]}')

    # Add End node and edge
    last_id = parsed[-1]["id"]
    nodes.append('End(["End"])')
    edges.append(f'{last_id} --> End')

    flowchart = "flowchart TD\n" + "\n".join(nodes + edges)
    annotation_block = "\n" + "\n".join(annotations)

    return flowchart + annotation_block

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)