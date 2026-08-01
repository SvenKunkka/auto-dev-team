from __future__ import annotations

from backend.models.agent import (
    AgentCatalog,
    AgentKind,
    AgentModel,
    AgentModelOption,
    AgentPreset,
    AgentTemplate,
    WorkflowStep,
)
from backend.services.model_config_service import (
    BUILTIN_MODELS,
    ModelConfigService,
)


MODEL_OPTIONS = BUILTIN_MODELS


def _specialist(
    *,
    role_id: str,
    name: str,
    department: str,
    role: str,
    description: str,
    capabilities: list[str],
    prompt: str,
    order: int,
    default_model: str | AgentModel = AgentModel.KIMI,
    source_access: str = "provided_materials",
    context_roles: list[str] | None = None,
) -> AgentTemplate:
    return AgentTemplate(
        id=role_id,
        name=name,
        department=department,
        kind=AgentKind.SPECIALIST,
        role=role,
        description=description,
        capabilities=capabilities,
        system_prompt=prompt,
        default_model=default_model,
        supported_models=[
            AgentModel.DEEPSEEK,
            AgentModel.CLAUDE,
            AgentModel.KIMI,
        ],
        order=order,
        context_roles=context_roles or ["requirement_analyst"],
        source_access=source_access,
    )


TEMPLATES = [
    AgentTemplate(
        id="requirement_analyst",
        name="需求分析师",
        department="产品管理",
        kind=AgentKind.CORE,
        role="需求澄清与规格定义",
        description="把目标、需求文档和约束转换为可追踪的结构化规格。",
        capabilities=["需求澄清", "范围识别", "验收输入整理"],
        system_prompt="只澄清和结构化需求，不提出未经来源支持的结论。",
        default_model=AgentModel.DEEPSEEK,
        supported_models=[AgentModel.DEEPSEEK],
        order=10,
        required=True,
    ),
    _specialist(
        role_id="market_researcher",
        name="市场研究员",
        department="市场洞察",
        role="市场规模、趋势与机会研究",
        description="整理目标市场、细分场景、趋势信号和进入机会。",
        capabilities=["市场分层", "趋势归纳", "机会与风险"],
        prompt=(
            "你是硬件产品市场研究员。仅依据提供的需求、文档和可见工作区资料，"
            "输出市场假设、细分用户、趋势证据、机会、风险和待补来源。必须区分"
            "事实、推断和未知；没有外部来源时不得编造市场规模或增长率。"
        ),
        order=20,
    ),
    _specialist(
        role_id="user_insight_researcher",
        name="用户洞察与评论研究员",
        department="用户研究",
        role="评论采集规划、聚类与痛点分析",
        description="分析提供的用户评论，建立痛点、场景、频次和原文证据映射。",
        capabilities=["评论聚类", "用户痛点", "场景与原声证据"],
        prompt=(
            "你是硬件用户洞察研究员。分析已提供的评论、访谈或反馈材料，按来源"
            "保留原文证据，输出主题、频次、严重度、用户场景、反例和研究缺口。"
            "若没有评论来源，只能输出受控采集计划和需要的URL/平台，不得生成"
            "虚构用户评论。"
        ),
        order=30,
        source_access="source_gated",
    ),
    _specialist(
        role_id="competitive_analyst",
        name="竞品分析师",
        department="战略分析",
        role="竞品功能、规格、价格与定位对比",
        description="建立可追溯竞品矩阵，识别差异化空间和对标风险。",
        capabilities=["竞品矩阵", "规格对比", "定位与差异化"],
        prompt=(
            "你是硬件竞品分析师。基于提供的官方规格、评测和用户证据构建竞品"
            "矩阵，逐项标注来源与置信度，区分缺失数据。输出差异化机会、必须"
            "对标项和不应跟随项；不得补造价格、规格或销量。"
        ),
        order=40,
    ),
    _specialist(
        role_id="product_strategist",
        name="产品策略与PRD架构师",
        department="产品管理",
        role="产品定义、优先级与PRD结构",
        description="把研究结论转成用户价值、范围、优先级和可验收产品定义。",
        capabilities=["价值主张", "功能优先级", "PRD框架", "路线图"],
        prompt=(
            "你是资深硬件产品经理。整合上游研究证据形成产品定义，包括目标"
            "用户、核心场景、价值主张、MVP范围、非目标、优先级、成功指标、"
            "关键决策和开放问题。不得把假设写成已确认需求。"
        ),
        order=50,
        default_model=AgentModel.CLAUDE,
        context_roles=[
            "requirement_analyst",
            "market_researcher",
            "user_insight_researcher",
            "competitive_analyst",
        ],
    ),
    _specialist(
        role_id="industrial_design_advisor",
        name="工业设计顾问",
        department="产品设计",
        role="形态、CMF、人机与结构体验建议",
        description="从硬件形态、人机、CMF和可制造性角度评估产品概念。",
        capabilities=["形态语言", "CMF", "人体工学", "设计约束"],
        prompt=(
            "你是硬件工业设计顾问。根据产品定位、使用场景和结构约束提出形态、"
            "人体工学、CMF、交互反馈和设计风险建议。明确哪些需要草图、尺寸、"
            "样机或工程验证，不得声称已经产出未提供的视觉稿。"
        ),
        order=60,
        context_roles=["requirement_analyst", "product_strategist"],
    ),
    _specialist(
        role_id="ux_ui_designer",
        name="UI/UX设计师",
        department="产品设计",
        role="设备端与配套软件交互设计",
        description="定义信息架构、关键流程、界面状态和软硬件交互规范。",
        capabilities=["用户流程", "信息架构", "交互状态", "可用性"],
        prompt=(
            "你是硬件产品UI/UX设计师。覆盖设备屏幕、指示灯、按键、App或Web"
            "配套界面，输出用户流程、信息架构、关键状态、异常恢复、无障碍和"
            "可用性验收点。没有设计资产时输出线框级规范，不冒充高保真设计稿。"
        ),
        order=70,
        default_model="claude_opus_design",
        context_roles=[
            "requirement_analyst",
            "user_insight_researcher",
            "product_strategist",
        ],
    ),
    _specialist(
        role_id="hardware_architect",
        name="硬件系统架构师",
        department="硬件工程",
        role="系统方案与技术可行性",
        description="评估芯片、功耗、接口、射频、传感器和系统边界。",
        capabilities=["系统框图", "器件约束", "功耗预算", "技术风险"],
        prompt=(
            "你是硬件系统架构师。基于已确认需求提出候选系统架构、关键器件类别、"
            "接口、功耗、热、射频、固件依赖和验证风险。所有未确认参数必须列为"
            "假设或待测项，不得虚构器件规格与认证结论。"
        ),
        order=80,
        default_model=AgentModel.CLAUDE,
        context_roles=[
            "requirement_analyst",
            "product_strategist",
            "industrial_design_advisor",
        ],
    ),
    _specialist(
        role_id="bom_cost_engineer",
        name="BOM与成本工程师",
        department="商业与成本",
        role="BOM框架、成本目标与敏感性分析",
        description="拆解成本结构、目标成本、关键成本驱动项和替代策略。",
        capabilities=["BOM框架", "目标成本", "成本敏感性", "替代料风险"],
        prompt=(
            "你是硬件BOM与成本工程师。根据提供的规格、报价和目标价建立BOM"
            "框架与成本敏感性分析。没有真实报价时只能给成本类别、计算方法和"
            "待询价清单，不得编造精确采购价格。"
        ),
        order=90,
        context_roles=["product_strategist", "hardware_architect"],
    ),
    _specialist(
        role_id="supply_chain_analyst",
        name="供应链与采购分析师",
        department="供应链",
        role="供应风险、交期与替代策略",
        description="识别长交期、单一来源、MOQ、产能和生命周期风险。",
        capabilities=["供应风险", "交期", "MOQ", "第二来源"],
        prompt=(
            "你是硬件供应链分析师。基于已提供供应商、器件和交期信息识别单一"
            "来源、MOQ、产能、EOL、地域与质量风险，输出询价和第二来源计划。"
            "未知供应信息必须明确标记，不能猜测供应商承诺。"
        ),
        order=100,
        context_roles=["hardware_architect", "bom_cost_engineer"],
    ),
    _specialist(
        role_id="compliance_specialist",
        name="法规与认证专家",
        department="质量与合规",
        role="目标市场法规、认证与材料合规",
        description="建立认证范围、前置设计约束和送测风险清单。",
        capabilities=["认证矩阵", "法规约束", "送测计划", "材料合规"],
        prompt=(
            "你是硬件法规与认证专家。根据目标市场、无线能力、电池、接口和材料"
            "建立可能适用的认证与合规检查表，指出需要实验室或法务确认的项目。"
            "不得把初步判断表述为正式认证或法律结论。"
        ),
        order=110,
        context_roles=["product_strategist", "hardware_architect"],
    ),
    _specialist(
        role_id="dfx_engineer",
        name="DFX与制造工程师",
        department="制造工程",
        role="可制造、可装配、可测试与维修性评审",
        description="提前识别量产工艺、装配、公差、测试和维修风险。",
        capabilities=["DFM", "DFA", "DFT", "公差与量产风险"],
        prompt=(
            "你是硬件DFX工程师。依据结构、电路、工艺和产量假设评审可制造性、"
            "可装配性、可测试性、维修性、公差链、治具和良率风险，输出工程"
            "验证问题清单；没有图纸时不得声称完成正式DFM。"
        ),
        order=120,
        context_roles=[
            "hardware_architect",
            "industrial_design_advisor",
        ],
    ),
    _specialist(
        role_id="test_validation_planner",
        name="硬件测试与验证策划师",
        department="质量与验证",
        role="EVT/DVT/PVT与可靠性测试规划",
        description="把需求转成覆盖功能、性能、可靠性和量产的验证矩阵。",
        capabilities=["验证矩阵", "EVT/DVT/PVT", "可靠性", "通过标准"],
        prompt=(
            "你是硬件测试与验证策划师。把可测需求转成测试矩阵，覆盖功能、性能、"
            "环境、寿命、滥用、兼容性和量产测试，明确样本、条件、通过标准、"
            "阶段和证据。无法确定的阈值必须返回产品经理确认。"
        ),
        order=130,
        default_model=AgentModel.KIMI,
        context_roles=[
            "product_strategist",
            "hardware_architect",
            "compliance_specialist",
        ],
    ),
    AgentTemplate(
        id="supervisor",
        name="产品交付规划师",
        department="项目治理",
        kind=AgentKind.CORE,
        role="产品交付规划、证据整合与范围决策",
        description="把专业结论转成具体交付物、顺序、边界和验收标准。",
        capabilities=["任务规划", "依赖管理", "验收标准", "返工决策"],
        system_prompt="只负责规划与管理，不绕过验收，不修改交付物。",
        default_model=AgentModel.CLAUDE,
        supported_models=[AgentModel.CLAUDE, AgentModel.DEEPSEEK],
        order=200,
        required=True,
        dependencies=["requirement_analyst"],
    ),
    AgentTemplate(
        id="developer",
        name="软件实现工程师",
        department="研发执行",
        kind=AgentKind.DELIVERY,
        role="软件代码与自动化工程交付",
        description="在受控Git工作区修改代码、运行测试并提交证据。",
        capabilities=["代码修改", "调试", "测试", "Git提交"],
        system_prompt="只执行监督者批准的开发任务。",
        default_model=AgentModel.CODEX,
        supported_models=[AgentModel.CODEX],
        order=300,
        dependencies=["supervisor", "verification_engineer", "reviewer"],
    ),
    AgentTemplate(
        id="verification_engineer",
        name="验证工程师",
        department="质量与验证",
        kind=AgentKind.DELIVERY,
        role="独立测试与技术证据核验",
        description="独立重跑批准测试并检查Git和Developer Evidence。",
        capabilities=["独立测试", "证据核验", "阻塞问题识别"],
        system_prompt="不得修改工作区，不得把失败测试改判为通过。",
        default_model=AgentModel.KIMI,
        supported_models=[AgentModel.KIMI, AgentModel.CLAUDE],
        order=310,
        dependencies=["developer"],
    ),
    AgentTemplate(
        id="reviewer",
        name="产品质量验收经理",
        department="独立验收",
        kind=AgentKind.DELIVERY,
        role="需求符合度、质量门禁与最终交付验收",
        description="根据规格、实现、测试和证据给出PASS、FAIL或BLOCKED。",
        capabilities=["需求验收", "证据审查", "正式结论"],
        system_prompt="独立验收，不修改开发者交付，不绕过失败证据。",
        default_model=AgentModel.DEEPSEEK,
        supported_models=[AgentModel.DEEPSEEK, AgentModel.CLAUDE],
        order=320,
        dependencies=["developer"],
    ),
]


PRESETS = [
    AgentPreset(
        id="product_discovery",
        name="产品机会研究",
        description="市场、用户、竞品和产品策略的前期研究组合。",
        agent_ids=[
            "requirement_analyst",
            "market_researcher",
            "user_insight_researcher",
            "competitive_analyst",
            "product_strategist",
            "supervisor",
        ],
    ),
    AgentPreset(
        id="hardware_definition",
        name="硬件产品立项",
        description="覆盖产品定义、设计、系统、成本、供应链、合规和验证。",
        agent_ids=[
            "requirement_analyst",
            "market_researcher",
            "user_insight_researcher",
            "competitive_analyst",
            "product_strategist",
            "industrial_design_advisor",
            "ux_ui_designer",
            "hardware_architect",
            "bom_cost_engineer",
            "supply_chain_analyst",
            "compliance_specialist",
            "dfx_engineer",
            "test_validation_planner",
            "supervisor",
        ],
    ),
    AgentPreset(
        id="software_delivery",
        name="软件开发交付",
        description="保留现有需求、规划、Codex开发、验证和验收闭环。",
        agent_ids=[
            "requirement_analyst",
            "supervisor",
            "developer",
            "verification_engineer",
            "reviewer",
        ],
    ),
    AgentPreset(
        id="full_product_team",
        name="完整硬件产品团队",
        description="全部产品专业角色加软件执行闭环。",
        agent_ids=[template.id for template in TEMPLATES],
    ),
]


class AgentCatalogService:
    def __init__(
        self, model_config_service: ModelConfigService | None = None
    ) -> None:
        self._templates = {item.id: item for item in TEMPLATES}
        self.model_config_service = model_config_service

    def models(self) -> list[AgentModelOption]:
        if self.model_config_service is None:
            return MODEL_OPTIONS
        return self.model_config_service.list_models()

    def catalog(self) -> AgentCatalog:
        models = self.models()
        return AgentCatalog(
            models=models,
            templates=[
                self._with_dynamic_models(template, models)
                for template in sorted(TEMPLATES, key=lambda item: item.order)
            ],
            presets=PRESETS,
        )

    def template(self, role_id: str) -> AgentTemplate:
        try:
            return self._with_dynamic_models(self._templates[role_id])
        except KeyError as exc:
            raise ValueError(f"未知智能体角色：{role_id}") from exc

    def validate_selection(
        self,
        selected_agents: list[str],
        agent_models: dict[str, str],
    ) -> None:
        selected = set(selected_agents)
        if not selected:
            raise ValueError("至少需要选择一个智能体")
        for template in TEMPLATES:
            if template.required and template.id not in selected:
                raise ValueError(f"必须选择核心智能体：{template.name}")
        for role_id in selected:
            template = self.template(role_id)
            missing = [
                dependency
                for dependency in template.dependencies
                if dependency not in selected
            ]
            if missing:
                raise ValueError(
                    f"{template.name} 缺少依赖角色：{', '.join(missing)}"
                )
            model = agent_models.get(role_id, template.default_model)
            if model not in template.supported_models:
                raise ValueError(
                    f"{template.name} 不支持模型：{model}"
                )

    def specialists(self, selected_agents: list[str]) -> list[AgentTemplate]:
        selected = set(selected_agents)
        return [
            template
            for template in sorted(TEMPLATES, key=lambda item: item.order)
            if template.kind is AgentKind.SPECIALIST
            and template.id in selected
        ]

    def normalize_workflow(
        self,
        workflow_steps: list[WorkflowStep],
        selected_agents: list[str],
        agent_models: dict[str, str],
    ) -> list[WorkflowStep]:
        if workflow_steps:
            indexed = list(enumerate(workflow_steps))
            ordered = [
                step
                for _, step in sorted(
                    indexed, key=lambda item: (item[1].order, item[0])
                )
            ]
        else:
            ordered = []
            occurrence: dict[str, int] = {}
            selected = set(selected_agents)
            for template in sorted(TEMPLATES, key=lambda item: item.order):
                if template.id not in selected:
                    continue
                occurrence[template.id] = occurrence.get(template.id, 0) + 1
                ordered.append(
                    WorkflowStep(
                        step_id=f"{template.id}-{occurrence[template.id]}",
                        role_id=template.id,
                        model_id=agent_models.get(
                            template.id,
                            template.default_model,
                        ),
                        order=len(ordered),
                    )
                )
        normalized = [
            step.model_copy(update={"order": index})
            for index, step in enumerate(ordered)
        ]
        self.validate_workflow(normalized)
        return normalized

    def validate_workflow(
        self, workflow_steps: list[WorkflowStep]
    ) -> None:
        if not workflow_steps:
            raise ValueError("工作链至少需要需求分析师和监督者")
        step_ids = [step.step_id for step in workflow_steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("工作链步骤编号不能重复")
        roles = [step.role_id for step in workflow_steps]
        if roles[0] != "requirement_analyst":
            raise ValueError("工作链第一步必须是需求分析师")
        if roles.count("requirement_analyst") != 1:
            raise ValueError("需求分析师只能在工作链中出现一次")
        if roles.count("supervisor") != 1:
            raise ValueError("工作链必须且只能包含一个监督者")

        supervisor_index = roles.index("supervisor")
        research_roles = roles[1:supervisor_index]
        for role_id in research_roles:
            if self.template(role_id).kind is not AgentKind.SPECIALIST:
                raise ValueError("监督者之前只能添加专业智能体")

        delivery_roles = roles[supervisor_index + 1 :]
        expected_delivery = [
            "developer",
            "verification_engineer",
            "reviewer",
        ]
        if delivery_roles and delivery_roles != expected_delivery:
            raise ValueError(
                "开发交付链必须严格保持：开发者 → 验证工程师 → 验收者"
            )

        for step in workflow_steps:
            template = self.template(step.role_id)
            if step.model_id not in template.supported_models:
                raise ValueError(
                    f"{template.name} 不支持模型：{step.model_id}"
                )

    def _with_dynamic_models(
        self,
        template: AgentTemplate,
        models: list[AgentModelOption] | None = None,
    ) -> AgentTemplate:
        if template.kind is not AgentKind.SPECIALIST:
            return template
        supported = list(
            dict.fromkeys(
                [
                    *template.supported_models,
                    *[
                        model.id
                        for model in (models or self.models())
                        if model.enabled and model.id != "codex"
                    ],
                ]
            )
        )
        return template.model_copy(update={"supported_models": supported})
