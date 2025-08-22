import os
from flask import Flask, request, jsonify
import ast

app = Flask(__name__)

@app.route('/')
def home():
    return "AI Agent is running!"

@app.route('/parse', methods=['POST'])
def parse():
    code = request.json.get('code', '')
    result = parse_code(code)
    return jsonify(result)

def parse_code(code):
    tree = ast.parse(code)
    parsed_lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            parsed_lines.append({"line": f"def {node.name}(...)", "symbol": "Subroutine"})
        elif isinstance(node, ast.If):
            parsed_lines.append({"line": "if ...", "symbol": "Decision"})
        elif isinstance(node, ast.Return):
            parsed_lines.append({"line": "return ...", "symbol": "Terminator"})
    return parsed_lines

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 10000))  # Render default
    app.run(host="0.0.0.0", port=port)