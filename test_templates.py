import os
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates'))
for template_name in os.listdir('templates'):
    if template_name.endswith('.html'):
        try:
            env.get_template(template_name)
            print(f"OK: {template_name}")
        except Exception as e:
            import traceback
            print(f"ERROR in {template_name}:")
            traceback.print_exc()
