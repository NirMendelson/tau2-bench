"""Extract tool signatures from AirlineTools to validate required parameters."""

import inspect
from typing import Optional, List
from pathlib import Path

from tau2.domains.airline.tools import AirlineTools
from tau2.domains.airline.data_model import FlightDB


class ToolSignatureCache:
    """Cache for tool signatures to avoid reloading on every validation."""
    
    def __init__(self):
        self._cache: Optional[dict[str, List[str]]] = None
        self._tools: Optional[AirlineTools] = None
    
    def _load_tools(self) -> AirlineTools:
        """Load AirlineTools instance."""
        if self._tools is None:
            from tau2.domains.airline.utils import AIRLINE_DB_PATH
            db = FlightDB.load(AIRLINE_DB_PATH)
            self._tools = AirlineTools(db)
        return self._tools
    
    def get_required_parameters(self, tool_name: str) -> Optional[List[str]]:
        """
        Get required parameters for a tool (parameters without default values).
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            List of required parameter names in order (excluding 'self'), or None if tool not found
        """
        if self._cache is None:
            self._cache = {}
            tools = self._load_tools()
            
            for name in tools.tools.keys():
                func = tools.tools[name]
                sig = inspect.signature(func)
                
                required_params = []
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    # If param.default is param.empty, it's required
                    if param.default is param.empty:
                        required_params.append(param_name)
                
                self._cache[name] = required_params
        
        return self._cache.get(tool_name)
    
    def tool_exists(self, tool_name: str) -> bool:
        """Check if a tool exists."""
        tools = self._load_tools()
        return tools.has_tool(tool_name)


# Global cache instance
_signature_cache = ToolSignatureCache()


def get_required_parameters(tool_name: str) -> Optional[List[str]]:
    """Get required parameters for a tool."""
    return _signature_cache.get_required_parameters(tool_name)


def tool_exists(tool_name: str) -> bool:
    """Check if a tool exists."""
    return _signature_cache.tool_exists(tool_name)

