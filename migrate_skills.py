import os
import shutil

source_dir = "/Users/pelayo/projects/agent-swarm-dev/skills"
dest_dir = "/Users/pelayo/projects/agent-swarm-dev/.agents/workflows"

skills = [
    ("mcp-builder", "mcp_builder_skill.md"),
    ("frontend-design", "frontend_design_skill.md"),
    ("skill-creator", "skill_creator_skill.md"),
    ("webapp-testing", "webapp_testing_skill.md"),
    ("rust-pro", "rust_pro_skill.md"),
    ("python-pro", "python_pro_skill.md"),
    ("typescript-pro", "typescript_pro_skill.md"),
    ("godot-gdscript-patterns", "godot_gdscript_patterns_skill.md"),
    ("multi-agent-patterns", "multi_agent_patterns_skill.md")
]

os.makedirs(dest_dir, exist_ok=True)

for skill_folder, dest_filename in skills:
    source_path = os.path.join(source_dir, skill_folder, "SKILL.md")
    dest_path = os.path.join(dest_dir, dest_filename)
    
    if not os.path.exists(source_path):
        print(f"Skipping {source_path}, does not exist.")
        continue

    with open(source_path, "r") as f:
        content = f.read()
    
    # Prepend YAML frontmatter if not present
    if not content.startswith("---"):
        skill_name = dest_filename.replace("_skill.md", "")
        frontmatter = f"---\ndescription: {skill_name}\n---\n\n"
        content = frontmatter + content
        
    with open(dest_path, "w") as f:
        f.write(content)
        
    print(f"Migrated {skill_folder} to {dest_filename}")

# Clean up original skills directory
shutil.rmtree(source_dir)
print("Removed temporary skills directory.")
