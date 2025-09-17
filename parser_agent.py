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
    edges = []
    node_counter = 0

    def new_node(label, shape):
        nonlocal node_counter
        label = sanitize_label(label)
        node_id = f"N{node_counter}"
        parsed_lines.append({"id": node_id, "line": label, "shape": shape})
        node_counter += 1
        return node_id

    def visit(node, parent_id=None):
        if isinstance(node, ast.FunctionDef):
            args = [arg.arg for arg in node.args.args]
            label = f"def {node.name}({', '.join(args)})"
            func_id = new_node(label, "subproc")
            if parent_id:
                edges.append((parent_id, "", func_id))
            prev_id = func_id
            for stmt in node.body:
                prev_id = visit(stmt, prev_id)
            return func_id

        elif isinstance(node, ast.If):
            label = f"if {ast.unparse(node.test)}"
            cond_id = new_node(label, "diamond")
            if parent_id:
                edges.append((parent_id, "", cond_id))
            yes_id = None
            no_id = None
            if node.body:
                yes_id = visit(node.body[0], cond_id)
                edges.append((cond_id, "Yes", yes_id))
                for i in range(1, len(node.body)):
                    yes_id = visit(node.body[i], yes_id)
            if node.orelse:
                no_id = visit(node.orelse[0], cond_id)
                edges.append((cond_id, "No", no_id))
                for i in range(1, len(node.orelse)):
                    no_id = visit(node.orelse[i], no_id)
            return cond_id

        elif isinstance(node, ast.For):
            label = f"for i in range(2, int(n ** 0.5) + 1)"
            loop_id = new_node(label, "hex")
            if parent_id:
                edges.append((parent_id, "", loop_id))
            body_start = visit(node.body[0], loop_id)
            edges.append((loop_id, "Yes", body_start))
            body_end = body_start
            for i in range(1, len(node.body)):
                body_end = visit(node.body[i], body_end)
            edges.append((body_end, "No", loop_id))  # loopback
            return loop_id

        elif isinstance(node, ast.Expr):
            label = ast.unparse(node)
            expr_id = new_node(label, "in-out")
            if parent_id:
                edges.append((parent_id, "", expr_id))
            return expr_id

        elif isinstance(node, ast.Return):
            label = "return"
            ret_id = new_node(label, "dbl-circ")
            if parent_id:
                edges.append((parent_id, "", ret_id))
            edges.append((ret_id, "", "End"))
            return ret_id

        else:
            last_id = parent_id
            for child in ast.iter_child_nodes(node):
                last_id = visit(child, last_id)
            return last_id

    start_id = "Start"
    parsed_lines.insert(0, {"id": start_id, "line": "Start", "shape": "circle"})
    parsed_lines.append({"id": "End", "line": "End", "shape": "circle"})

    for node in tree.body:
        visit(node, start_id)

    return parsed_lines, edges

def generate_mermaid_flowchart(code):
    nodes, edges = parse_code(code)
    node_lines = [f'{n["id"]}["{n["line"]}"]' for n in nodes]
    shape_lines = [f'{n["id"]}@{{ shape: {n["shape"]} }}' for n in nodes]
    edge_lines = []
    for src, label, tgt in edges:
        if label:
            edge_lines.append(f"{src} -->|{label}| {tgt}")
        else:
            edge_lines.append(f"{src} --> {tgt}")
    return "flowchart TD\n" + "\n".join(node_lines + edge_lines + shape_lines)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)