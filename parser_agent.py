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

# Sanitize labels for Mermaid compatibility
def sanitize_label(label):
    return (
        label.replace('"', "'")
             .replace("{", "{")
             .replace("}", "}")
             .replace("\\n", " ")
    )

# Parse Python code into AST and build flowchart nodes/edges
def parse_code(code):
    tree = ast.parse(code)
    nodes = []
    edges = []
    node_counter = 0

    def new_node(label, shape):
        nonlocal node_counter
        label = sanitize_label(label)
        node_id = f"N{node_counter}"
        nodes.append({"id": node_id, "line": label, "shape": shape})
        node_counter += 1
        return node_id

    def visit(node, parent_id=None):
        if isinstance(node, ast.FunctionDef):
            args = [arg.arg for arg in node.args.args]
            label = f"def {node.name}({', '.join(args)})"
            func_id = new_node(label, "subproc")
            edges.append(("Start", "", func_id))
            prev_id = func_id
            for stmt in node.body:
                prev_id = visit(stmt, prev_id)
            return prev_id

        elif isinstance(node, ast.If):
            label = f"if {ast.unparse(node.test)}"
            cond_id = new_node(label, "diamond")
            edges.append((parent_id, "", cond_id))
            yes_id = visit(node.body[0], cond_id)
            edges.append((cond_id, "Yes", yes_id))
            for i in range(1, len(node.body)):
                yes_id = visit(node.body[i], yes_id)
            if node.orelse:
                no_id = visit(node.orelse[0], cond_id)
                edges.append((cond_id, "No", no_id))
                for i in range(1, len(node.orelse)):
                    no_id = visit(node.orelse[i], no_id)
            else:
                # If no explicit else, link to next block
                edges.append((cond_id, "No", None))  # Placeholder
            return cond_id

        elif isinstance(node, ast.For):
            label = f"for i in range(2, int(n ** 0.5) + 1)"
            loop_id = new_node(label, "hex")
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
            edges.append((parent_id, "", expr_id))
            return expr_id

        elif isinstance(node, ast.Return):
            label = "return"
            ret_id = new_node(label, "dbl-circ")
            edges.append((parent_id, "", ret_id))
            edges.append((ret_id, "", "End"))
            return ret_id

        else:
            last_id = parent_id
            for child in ast.iter_child_nodes(node):
                last_id = visit(child, last_id)
            return last_id

    nodes.insert(0, {"id": "Start", "line": "Start", "shape": "circle"})
    nodes.append({"id": "End", "line": "End", "shape": "circle"})

    for node in tree.body:
        visit(node, "Start")

    # Fix placeholder edges
    for i, (src, label, tgt) in enumerate(edges):
        if tgt is None:
            # Find next node after src
            src_index = next((j for j, n in enumerate(nodes) if n["id"] == src), None)
            if src_index is not None and src_index + 1 < len(nodes):
                edges[i] = (src, label, nodes[src_index + 1]["id"])

    return nodes, edges

# Generate Mermaid flowchart from nodes and edges
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