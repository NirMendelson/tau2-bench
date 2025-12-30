# CSPL Validator (YAML)

## Goal
Catch CSPL mistakes **before runtime** with red squiggles in the editor.

This is **not an executor**.  
It only **validates** CSPL YAML files.

## What it checks
- ❌ Invalid or missing fields (schema validation)
- ❌ Invalid step types or actions
- ❌ Using a variable before it is declared
- ❌ Referencing unknown variables
- ❌ Invalid step structure by type 

## Core Functionalities
- make sure when we use a tool we pass it all of the required parameters
- make sure the fields are correct
- make sure we do not use any parameters before declaring them

## How it works
- Uses a **YAML schema** for structural validation
- Uses a **custom editor validator** (Cursor / VSCode) for semantic rules
- Parses YAML → analyzes steps top-to-bottom → reports diagnostics

## Result
- Red squiggles under bad lines
- Clear error messages in the Problems panel
- Fast feedback while editing CSPL

## Critical
the linter should work only on workflow.yaml inside airline/codebase folder.
the tools use use are in domain/airline/tools


## tasks
[] look for contradictions in the workflow.yaml
[] decide on rules


## rules
1. make sure that we pass required parameters to tools
2. make sure we don't use parameters without declaring them