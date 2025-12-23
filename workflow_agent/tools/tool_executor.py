import inspect
from typing import Any, Callable, Dict, List, Optional
from loguru import logger

from tau2.environment.tool import Tool


def get_tool_function(tool: Tool) -> Callable:
    """
    Extracts the actual function from a Tool object.
    
    Args:
        tool: The Tool object
        
    Returns:
        The underlying function that the tool wraps
    """
    return tool._func


def get_function_parameters(func: Callable) -> List[str]:
    """
    Gets the parameter names of a function in order, excluding 'self'.
    
    Args:
        func: The function to inspect
        
    Returns:
        List of parameter names in order
    """
    sig = inspect.signature(func)
    params = []
    for param_name, param in sig.parameters.items():
        # Skip 'self' parameter
        if param_name != 'self':
            params.append(param_name)
    return params


def map_input_to_kwargs(input_list: List[Any], param_names: List[str]) -> Dict[str, Any]:
    """
    Maps a list of input values to keyword arguments based on parameter names.
    
    Args:
        input_list: List of input values from workflow
        param_names: List of parameter names from function signature
        
    Returns:
        Dictionary mapping parameter names to values
        
    Raises:
        ValueError: If input_list length doesn't match param_names length
    """
    if len(input_list) != len(param_names):
        raise ValueError(
            f"input list length ({len(input_list)}) doesn't match "
            f"function parameters ({len(param_names)}): {param_names}"
        )
    
    return dict(zip(param_names, input_list))


def call_tool_with_input(tool: Tool, input_list: List[Any]) -> Any:
    """
    Calls a tool with an input list, mapping it to the function's parameters.
    
    Args:
        tool: The Tool object to call
        input_list: List of input values from workflow
        
    Returns:
        The result of the tool call
    """
    func = get_tool_function(tool)
    param_names = get_function_parameters(func)
    kwargs = map_input_to_kwargs(input_list, param_names)
    
    return func(**kwargs)


def call_tool_with_kwargs(tool: Tool, kwargs: Dict[str, Any]) -> Any:
    """
    Calls a tool with keyword arguments directly.
    
    Args:
        tool: The Tool object to call
        kwargs: Dictionary of keyword arguments
        
    Returns:
        The result of the tool call
    """
    func = get_tool_function(tool)
    return func(**kwargs)


def call_tool(tool: Tool, input_list: Optional[List[Any]] = None, kwargs: Optional[Dict[str, Any]] = None) -> Any:
    """
    Calls a tool with either input list or keyword arguments.
    If both are provided, input_list takes precedence.
    
    Args:
        tool: The Tool object to call
        input_list: Optional list of input values (positional)
        kwargs: Optional dictionary of keyword arguments
        
    Returns:
        The result of the tool call
        
    Raises:
        ValueError: If neither input_list nor kwargs are provided
    """
    if input_list is not None:
        return call_tool_with_input(tool, input_list)
    elif kwargs is not None:
        return call_tool_with_kwargs(tool, kwargs)
    else:
        raise ValueError("Either input_list or kwargs must be provided")


class ToolExecutor:
    """
    Executes tools from workflow syntax, handling the mapping between
    workflow 'input' lists and actual tool function parameters.
    """
    
    def __init__(self, tools_list: List[Tool]):
        """
        Initializes the ToolExecutor with a list of Tool objects.
        
        Args:
            tools_list: List of Tool objects from the environment
        """
        self.tools = {}
        for tool in tools_list:
            self.tools[tool.name] = tool
    
    def has_tool(self, tool_name: str) -> bool:
        """
        Checks if a tool exists.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if tool exists, False otherwise
        """
        return tool_name in self.tools
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        Gets a tool by name.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            The Tool object or None if not found
        """
        return self.tools.get(tool_name)
    
    def execute(self, tool_name: str, input_list: Optional[List[Any]] = None, **kwargs) -> Any:
        """
        Executes a tool by name with either input list or keyword arguments.
        
        Args:
            tool_name: Name of the tool to execute
            input_list: Optional list of input values (from workflow 'input' field)
            **kwargs: Optional keyword arguments (from workflow step fields)
            
        Returns:
            The result of the tool execution
            
        Raises:
            ValueError: If tool not found or if neither input_list nor kwargs provided
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        tool = self.tools[tool_name]
        
        # If input_list is provided, use it (workflow syntax)
        # Otherwise, use kwargs
        if input_list is not None:
            return call_tool_with_input(tool, input_list)
        elif kwargs:
            return call_tool_with_kwargs(tool, kwargs)
        else:
            raise ValueError(f"Either input_list or kwargs must be provided for tool '{tool_name}'")
    
    def __getattr__(self, name: str) -> Any:
        """
        Allows accessing tools as attributes (e.g., executor.get_user_details).
        This maintains backward compatibility with the old ToolBridge approach.
        
        Args:
            name: Tool name
            
        Returns:
            A callable that executes the tool
        """
        if name in self.tools:
            tool = self.tools[name]
            # Return a callable that can be called with input_list or kwargs
            def tool_wrapper(*args, **kwargs):
                if args and not kwargs:
                    # If only positional args, treat as input_list
                    return call_tool_with_input(tool, list(args))
                elif kwargs:
                    return call_tool_with_kwargs(tool, kwargs)
                else:
                    return call_tool_with_input(tool, [])
            
            return tool_wrapper
        
        raise AttributeError(f"Tool '{name}' not found")

