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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)