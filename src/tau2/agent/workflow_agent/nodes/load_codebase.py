from pathlib import Path
from pocketflow import Node
from loguru import logger

from tau2.utils.utils import DATA_DIR
from tau2.utils.io_utils import load_file
from ..utils.workflow_parser import load_workflows, load_constants


class LoadCodebaseNode(Node):
    """
    Node that loads codebase files (workflow.yaml, tone.yaml, constants.yaml)
    from the domain's codebase folder and stores them in the shared store.
    """
    
    def prep(self, shared):
        # Get domain from shared store (passed from WorkflowAgent)
        domain = shared.get("domain")
        if not domain:
            logger.error("domain not found in shared store")
            return None
        
        # Construct codebase directory path
        codebase_dir = DATA_DIR / "tau2" / "domains" / domain / "codebase"
        
        return codebase_dir
    
    def exec(self, codebase_dir):
        if codebase_dir is None:
            return {
                "workflows": {},
                "tone_config": {},
                "constants": {}
            }
        
        codebase_dir = Path(codebase_dir)
        
        # Check if codebase directory exists
        if not codebase_dir.exists():
            logger.warning(f"codebase directory does not exist: {codebase_dir}")
            return {
                "workflows": {},
                "tone_config": {},
                "constants": {}
            }
        
        # Define file paths
        workflow_path = codebase_dir / "workflow.yaml"
        tone_path = codebase_dir / "tone.yaml"
        constants_path = codebase_dir / "constants.yaml"
        
        # Load workflow.yaml using workflow_parser.load_workflows
        # This handles multiple workflows separated by '---'
        workflows = {}
        if workflow_path.exists():
            try:
                workflows = load_workflows(str(workflow_path))
                logger.info(f"loaded {len(workflows)} workflow(s) from {workflow_path}")
            except Exception as e:
                logger.error(f"error loading workflow.yaml: {e}")
        else:
            logger.warning(f"workflow.yaml not found at {workflow_path}")
        
        # Load tone.yaml
        tone_config = {}
        if tone_path.exists():
            try:
                tone_config = load_file(tone_path)
            except Exception as e:
                logger.error(f"error loading tone.yaml: {e}")
        else:
            logger.warning(f"tone.yaml not found at {tone_path}")
        
        # Load constants.yaml using workflow_parser.load_constants
        constants = {}
        if constants_path.exists():
            try:
                constants = load_constants(str(constants_path))
            except Exception as e:
                logger.error(f"error loading constants.yaml: {e}")
        else:
            logger.warning(f"constants.yaml not found at {constants_path}")
        
        return {
            "workflows": workflows,
            "tone_config": tone_config,
            "constants": constants
        }
    
    def post(self, shared, prep_res, exec_res):
        # Store codebase data in shared store
        shared["workflows"] = exec_res.get("workflows", {})
        shared["tone_config"] = exec_res.get("tone_config", {})
        shared["constants"] = exec_res.get("constants", {})
        
        # Also handle current_entry if it exists (for backward compatibility)
        # This allows the node to also set up conversation_history from current_entry
        entry = shared.get("current_entry")
        if entry:
            user_input = entry.get("input", "")
            if user_input and not shared.get("conversation_history"):
                shared["conversation_history"] = [
                    {"role": "user", "content": user_input}
                ]
        
        return "default"
