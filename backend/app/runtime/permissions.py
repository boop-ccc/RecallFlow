class ToolPermissionDenied(RuntimeError):
    """
    Agent 尝试调用未授权工具。
    """

    def __init__(
        self,
        *,
        agent_name: str,
        tool_name: str,
    ) -> None:
        self.agent_name = agent_name
        self.tool_name = tool_name

        super().__init__(
            f"Agent '{agent_name}' "
            f"没有权限调用工具 '{tool_name}'"
        )


DEFAULT_TOOL_PERMISSIONS: dict[
    str,
    set[str],
] = {
    # Supervisor 负责调度，
    # 第一版不允许直接碰业务工具。
    "supervisor": set(),

    # 私有历史域
    "memory_agent": {
        "search_memory",
    },

    # 公共网络域
    "research_agent": {
        "web_search",
        "fetch_page",
    },

    # Verifier 后续只做证据验证，
    # 不直接开放私人检索或 Web Search。
    "verifier_agent": set(),
}


class PermissionPolicy:
    """
    Capability-based Tool Permission
    = 基于能力的工具权限。

    核心思想：

    不是“所有 Agent 都可以调用所有工具”，
    而是每个 Agent 只拥有完成职责所必需的能力。
    """

    def __init__(
        self,
        permissions: dict[
            str,
            set[str],
        ]
        | None = None,
    ) -> None:
        source = (
            permissions
            or DEFAULT_TOOL_PERMISSIONS
        )

        # copy，避免外部修改默认集合
        self.permissions = {
            agent: set(tools)
            for agent, tools
            in source.items()
        }

    def allowed_tools(
        self,
        agent_name: str,
    ) -> set[str]:
        return set(
            self.permissions.get(
                agent_name,
                set(),
            )
        )

    def is_allowed(
        self,
        *,
        agent_name: str,
        tool_name: str,
    ) -> bool:
        return (
            tool_name
            in self.allowed_tools(
                agent_name
            )
        )

    def require(
        self,
        *,
        agent_name: str,
        tool_name: str,
    ) -> None:
        if not self.is_allowed(
            agent_name=agent_name,
            tool_name=tool_name,
        ):
            raise ToolPermissionDenied(
                agent_name=agent_name,
                tool_name=tool_name,
            )
