#!/usr/bin/env python3
"""
Migration script to convert workflow YAML format:
1. Transforms top-level workflow/subworkflow dict into a list: [metadata, step1, step2, ...]
2. Removes redundant 'steps:' wrappers from then/else blocks.
3. Reduces indentation.
"""

from ruamel.yaml import YAML
import sys
from ruamel.yaml.comments import CommentedMap, CommentedSeq

def migrate_branching(obj):
    """Recursively remove 'steps:' wrapper from then/else blocks."""
    if isinstance(obj, dict):
        for key in ['then', 'else']:
            if key in obj:
                block = obj[key]
                if isinstance(block, dict) and 'steps' in block:
                    # Replace the dict with just the steps array
                    obj[key] = block['steps']
                    # Recursively process the new list
                    migrate_branching(obj[key])
                else:
                    # Recursively process the existing block
                    migrate_branching(block)
        
        # Process all other dict values
        for key, value in obj.items():
            if key not in ['then', 'else']:
                migrate_branching(value)
    
    elif isinstance(obj, list):
        for item in obj:
            migrate_branching(item)

def migrate_workflow(doc):
    """Converts a workflow document to the new list-based format."""
    if not isinstance(doc, dict):
        return doc
    
    # Metadata keys
    metadata_keys = ['workflow', 'subworkflow', 'when', 'keywords', 'examples', 'description']
    metadata = CommentedMap()
    for key in metadata_keys:
        if key in doc:
            metadata[key] = doc[key]
    
    steps = doc.get('steps', [])
    
    # Create the new list
    new_doc = CommentedSeq()
    new_doc.append(metadata)
    
    # Add steps
    for step in steps:
        migrate_branching(step)
        new_doc.append(step)
    
    # Preserve comments from original doc to metadata? 
    # ruamel.yaml handles comments on keys, which is tricky during conversion.
    
    return new_doc

def main():
    if len(sys.argv) != 2:
        print("Usage: python remove_steps_wrapper.py <workflow.yaml>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    # Load YAML with ruamel to preserve formatting
    yaml = YAML()
    yaml.preserve_quotes = True
    # Reduced indentation for the new list format
    yaml.indent(mapping=2, sequence=2, offset=0)
    
    # Load all documents
    with open(file_path, 'r') as f:
        documents = list(yaml.load_all(f))
    
    # Process each document
    migrated_docs = []
    for doc in documents:
        if doc:
            # Check if it's already migrated (is a list)
            if isinstance(doc, list):
                # Just fix branching inside
                migrate_branching(doc)
                migrated_docs.append(doc)
            else:
                migrated_docs.append(migrate_workflow(doc))
    
    # Save back to file
    with open(file_path, 'w') as f:
        yaml.dump_all(migrated_docs, f)
    
    print(f"Successfully migrated {file_path} to the new format.")

if __name__ == '__main__':
    main()
