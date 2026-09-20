---
name: autumn-recruitment-tracker
description: >
  监控全国范围校园招聘中新开放的正式校招岗位，目标岗位方向/届别/招聘季节/是否含实习
  均由 config.json 配置驱动，可用于任意行业方向。首次使用时会主动向用户提问确认这些
  设置，不预设任何默认方向。去重后生成日报。当需要手动触发一次监控、检查监控状态、
  或修改监控方向/关键词/公司范围时使用此技能。
metadata:
  author: community
  version: "1.0.0"
---

# 秋招岗位监控

目录约定（不要写死用户名、家目录或安装位置）：

```
SKILL_DIR=.
```

执行本文件中的命令时，以当前这份 `SKILL.md` 所在目录作为工作目录，并使用相对于该目录的路径。所有配置、状态、脚本和参考文档都从这里解析，禁止使用发布者机器上的绝对路径或固定技能 ID。

- 配置：`$SKILL_DIR/config.json`（目标届别/季节/岗位方向/是否含实习/关键词，全部在这里改，不需要碰代码或其他文档；首次使用时该文件可能不存在或 `onboarded` 为 `false`，见第 0 步）、`$SKILL_DIR/config.example.json`（未初始化时的模板，不要直接改这个文件）
- 状态：`$SKILL_DIR/state/seen_postings.json`
- 脚本：`$SKILL_DIR/scripts/dedupe.py`、`$SKILL_DIR/scripts/annotate.py`、`$SKILL_DIR/scripts/digest.py`
- 参考文档：`$SKILL_DIR/references/sources.md`（数据源与兜底策略）、
  `$SKILL_DIR/references/keyword-filters.md`（岗位方向/实习/届别过滤逻辑，具体关键词读 config.json）、
  `$SKILL_DIR/references/company-watchlist.md`（27届校招、大厂和央国企重点观察清单）、
  `$SKILL_DIR/references/high-growth-company-discovery.md`（高风险高成长公司增量发现、证据、风险、观察池和反向查岗规则）、
  `$SKILL_DIR/references/digest-format.md`（日报格式，仅供理解 `digest.py` 输出，不需要手写格式化逻辑）。

如果本次运行是定时任务（无人值守）：**不要**使用 AskUserQuestion 或以任何方式等待用户输入；遇到不确定情况一律按本文件和 references 中的默认策略自主处理，并在最终回复里如实说明做了什么假设。（第 0 步的初始化提问例外——那一步专门规定了无人值守场景下应该怎么做，见下文。）

## 执行步骤

### 0. 首次使用初始化（仅当尚未完成初始化时触发）

读取 `$SKILL_DIR/config.json`；如果这个文件不存在，先把 `$SKILL_DIR/config.example.json` 复制一份成 `$SKILL_DIR/config.json`。

检查 `onboarded` 字段：

- **如果 `onboarded` 不是 `true`，且当前是有用户在场的交互式会话**（不是无人值守的定时任务）：这是用户第一次使用这个技能，此时**不要**凭空瞎猜方向直接开始搜索，必须先通过对话（优先用 AskUserQuestion 等提问工具，没有就直接用文字提问）向用户确认这几个找工作的人最关心的问题：
  1. **目标届别**——比如"2027届"，也可以是社招/无届别限制。
  2. **想投递的行业/岗位方向**——用大白话描述就行，比如"技术开发，前端后端都要"、"市场营销"、"财务"、"不限方向"。不需要用户自己列关键词——拿到回答后，由你自己根据这个行业方向的常见细分职能，归纳出一组合理的 `positive_keywords`（覆盖该方向常见的岗位名称/职能词）、可选的 `fuzzy_keywords`（比如笼统的"管理培训生"）、以及几个明显不相关方向作为 `negative_keywords` 兜底。
  3. **要不要包含实习岗位**——只要正式校招，还是也要看实习/实习转正。
  4. **对应的招聘季节**——比如"2026秋招"还是"2026春招"，用于生成 `target_season_label`；并据此推算一个合理的 `season_end_date`（这一季大概什么时候结束、该归档重来，秋招一般到次年2月左右，春招一般到当年7月左右，不需要再单独问用户，除非用户主动想自定义）。

   问完之后，把这些信息写进 `$SKILL_DIR/config.json`（`target_grad_year`、`target_season_label`、`season_end_date`、`job_category_label`、`include_internships`、`job_filter.positive_keywords`/`fuzzy_keywords`/`negative_keywords`），并把 `onboarded` 设为 `true`。`job_filter.intern_exclusion_keywords` 和 `job_filter.formal_recruit_keywords` 这两组是通用的，`config.example.json` 里已经有合理默认值，一般不需要改。写完后用一段话跟用户确认一遍设置摘要，再继续往下执行第 1 步。

- **如果 `onboarded` 不是 `true`，但当前是无人值守的定时任务运行**：说明用户还没有完成初始化设置。不要凭空猜测方向瞎跑一通。直接在最终回复里如实说明"这个技能还没有完成初始化设置，请先手动运行一次、回答几个方向设置问题后再启用定时任务"，然后结束本次运行，不要往下执行发现流程。

- **如果 `onboarded` 已经是 `true`**：跳过这一步，直接进入第 1 步。

### 0.5 首次全量检索（核心体验保证）

首次完成初始化后，必须执行一次全量检索，不能把“新增岗位”逻辑误当成首次运行逻辑。全量检索必须覆盖第 2 步列出的全部四组来源、公司官网/官方 ATS 核验、高成长公司增量层和牛客入口逐企业复核（若已启用），并将当前仍有效的全部匹配岗位写入候选主表。

首次全量检索时：

- `state/seen_postings.json` 不得用于缩减来源覆盖或跳过公司；它只用于记录首次检索结果，后续运行再据此识别新增、已见和过期岗位。
- 必须先建立完整的当前候选基线，再生成“新增岗位”日报；首次运行的新增数可以等于基线岗位数。
- 必须保留每条记录的来源、官网核验结果、岗位链接选择理由和过滤标注，确保用户第一次看到的结果就是完整可用的岗位集合。
- 即使某一来源组暂时不可访问，也要继续完成其他来源组，并在日报中报告该组的缺口和下一步复核动作。

后续运行才按第 1.5 步复核存量、按第 2 步发现增量，并用去重状态计算真正新增。

### 1. 读取配置

读取 `$SKILL_DIR/config.json`，获取 `target_grad_year`（目标届别）、`target_season_label`（季节标签）、`job_category_label`（岗位方向标签，例如"财务"）、`include_internships`（是否也要看实习）、`job_filter`（正向/模糊/负向/实习排除/正式校招确认关键词）、`priority_monitoring`（27届校招、央国企、重点公司）、`nowcoder_entry_audit`（牛客入口逐企业复核）和 `high_growth_company_discovery`（高风险高成长公司增量发现）等参数，供后续所有 prompt 使用。下文所有 `{job_category_label}`、`{target_grad_year}` 均指代这里读到的实际值。优先关注 2027 届校招正式批/提前批和央国企技术校招；高成长公司发现只能叠加，不能替换或缩减现有搜索逻辑。

### 1.5 复核当前岗位

在发现新增岗位前，读取输出目录中的当前候选列表并逐条复核来源页。只有来源页明确显示招聘截止日期早于当天、职位已下线/停止招聘/不存在，或 HTTP 状态为 404/410 时才判定过期；临时网络错误、登录限制、验证码、反爬、超时或无法确认一律保留。确定过期的记录必须按 `company + title + source_url` 从当前候选和 `state/seen_postings.json` 同步删除；若状态 URL 已清理查询参数，再以 `company + title` 复核后删除。

当前表中仍使用牛客链接的岗位，也必须执行 `references/sources.md` 的“牛客岗位官网链接优先”规则：先核实官网对应岗位或目标届别校招是否开放，有可核实官方入口就更新岗位链接，否则保留牛客链接并记录原因。目标届别读取 `config.json.target_grad_year`（如 2027），不固定写死。仅换成同一岗位的官网链接属于链接更新，不计新增，不重置原有处理状态。

### 2. 并行发现（4 个子 agent）

先读 `$SKILL_DIR/references/sources.md`，按其中的来源分组，用 Agent 工具在**同一条消息里并行**发起 4 个子任务（general-purpose 类型，需要能用 Skill/WebSearch/WebFetch 等联网工具）。四组既有来源必须全部保留；若 `high_growth_company_discovery.enabled=true`，同时完整读取 `$SKILL_DIR/references/high-growth-company-discovery.md`，把公司先行发现作为每组的增量输出，不能改成只找高成长公司：

1. 牛客网 求职/校招板块
2. 公司招聘微信公众号 + 官网详情（搜索"XX招聘"公众号发布的秋招公告，跳转官网核实岗位）—— 这是中国大陆校招信息发布的一手链路，优先级高
3. 51job校园招聘 + 智联招聘校园 + 猎聘校园官方频道（合并一个子任务）
4. 门户/公众号"秋招名单/时间表"汇总贴 + 实习僧(shixiseng.com)（WebSearch 发现新公司名单）

每个子 agent 的 prompt 必须：
- 显式包含「必须加载 web-access skill 并遵循指引」这句话。
- 用目标性措辞下达任务，把 config.json 里的 `job_category_label`、`target_grad_year` 实际值代入（例如："调研牛客网上有哪些{job_category_label}方向的{target_grad_year}届秋招正式岗位，覆盖全国范围"），不要指定具体方法动词（不要写"用WebSearch搜索"之类）。
- 要求返回结构化列表，字段：`company`（公司名称）、`title`（职位名称）、`city`（工作城市，无法判断写"未注明"）、`highlight`（岗位亮点，一句话）、`source_url`（最终优先投递链接，保留完整参数）、`source_platform`（最终链接所属平台）。牛客发现的岗位必须执行 `references/sources.md` 的“牛客岗位官网链接优先”规则，并返回其中规定的原始发现链接、官网核实结果与证据字段；该规则同样适用于其他来源组遇到的牛客链接。
- 启用高成长公司增量层时，除岗位列表外另行返回 `growth_company_leads`，字段和证据门槛严格遵循 `references/high-growth-company-discovery.md`；公司线索不能混进岗位列表，也不能因为增量层而减少原来源岗位覆盖。
- 说明：若该来源当天无法访问或没有相关信息，直接如实汇报为空，不要反复重试同一种方式。
- **显式禁止子 agent 再自行派发下一层子 agent**（写清楚"必须自己直接完成调研，不得再调用 Agent 工具委托其他子 agent"）。实测发现子 agent 会倾向于"逐个公司开子任务核实"，导致任务树无限展开、耗时和成本失控。正确做法是用该平台自身的搜索/筛选/关键词功能一次性检索，而不是一家家公司点开核实。
- 给每个子 agent 一个明确的范围上限提示，例如"最多深入核实10-15家最相关的公司，覆盖面比逐一核实的精确度更重要"，避免无限深挖单一路径。

#### 牛客入口逐企业复核（强制，不适用上述范围上限）

当 `config.json.nowcoder_entry_audit.enabled` 为 `true` 时，牛客子任务必须额外完成以下流程：

1. 枚举当天在牛客 **校招日程、秋招日报/速递、校招专场、校招首页和搜索结果页** 中可见的每一个"一键投递"或企业招聘入口；同一公司多个入口可合并，但必须保留全部入口 URL。
2. 对枚举出的**每家公司逐一**进入牛客职位页或跳转的官方招聘系统，检查其当前 2027 届正式校招、提前批、实习/可转正岗位。不得因为入口文案未包含目标关键词、公司不在 watchlist、公司此前已出现，或当日候选数已达到某个数量而跳过。
3. **公众号只用于发现公司，不能作为核实终点。** 只要牛客入口或公众号文章出现一家公司，无论公众号文章能否打开、是否要求验证、是否被删除、是否没有投递链接，都必须继续按公司名称定位其官网“加入我们/人才招聘/校园招聘”页面或官方招聘系统（含公司委托的北森、大易、Moka、飞书招聘、智联、51job 等 ATS），检查当前岗位列表。公众号访问受限不能直接结束该公司的复核，也不能直接写成最终的“访问受限”。
4. 只有已经实际尝试公司官网/官方招聘系统后，才能给该公司收口：
   - 官网岗位列表可访问且已检查：按结果写 `新增候选`、`已有岗位`、`无目标岗位` 或 `职责不完整`；仅凭公众号文案不得写 `无目标岗位`。
   - 官网或官方招聘系统也遇到登录、验证码、反爬、超时、动态接口无法解析：写 `访问受限`，保留到下一次运行；必须具体记录受限原因和下一步，不能只写四个字“访问受限”。
   - 官网明确不存在、招聘入口明确失效或返回 404/410：才写 `入口失效`。公众号文章被删除不等于公司官网招聘入口失效。
5. 只将职责完整、届别符合、方向通过过滤规则的职位纳入候选；但所有被检查公司都必须写入 `$SKILL_DIR/../output/nowcoder-entry-audit-current.json`，至少包括 `company`、`entry_urls`、`entry_source`、`checked_at`、`result`（`新增候选`/`已有岗位`/`无目标岗位`/`职责不完整`/`访问受限`/`入口失效`）、`matched_titles`、`wechat_url`、`official_url`、`official_search_attempted`、`official_check_result`、`access_reason` 和 `next_action`。其中：
   - `official_search_attempted` 只有在公司官网或官方 ATS 已实际尝试后才能为 `true`；公众号文章本身不算官网尝试。
   - `access_reason` 使用具体原因，例如“官网 ATS 要求登录”“官网触发验证码”“官网岗位接口动态渲染无法解析”“仅找到同名公司，官方主体待确认”，不得笼统填写“访问受限”。
   - `next_action` 写明下一轮应继续检查的官网入口或待解决问题；已完成官网核实的记录可留空。
6. 本轮结束前必须检查：所有当天可见公司都已经 `official_search_attempted=true`。只要还有公众号线索未尝试官网，就不算完成“逐一复核”，不得结束牛客子任务。
7. 日报必须报告“牛客入口：已枚举 X 家，公众号线索 X 家，官网已尝试 X 家，逐一复核 X 家，待复核 X 家”，并分别列出“官网未尝试”和“官网已尝试但仍受限”的数量。没有此统计不得结束本次运行。

该规则优先于“最多深入核实10-15家”的一般范围建议；范围建议只约束其他发现来源，不能用于缩减当天牛客可见企业入口的逐一复核范围。

等待 4 个子 agent 全部返回。某个子 agent 为空或失败不影响其余结果的处理——继续往下走，不要中断整体流程。

### 2.5 高成长公司观察池与反向查岗（启用时强制）

当 `high_growth_company_discovery.enabled=true` 时，合并四组的 `growth_company_leads`，按公司名和别名去重，并严格执行 `$SKILL_DIR/references/high-growth-company-discovery.md`：

1. 证据不足、只有股价/融资传闻/媒体榜单或只有创始人财富的线索不得标成已确认高成长公司；可以低可信度留待补证，但必须写清缺口。
2. 按配置上限优先深入复核新发现、高分、广州/深圳和方向最相关的公司，实际尝试官网、招聘公众号或官方 ATS；访问受限、验证码、反爬和网络错误只记具体原因及下一步，不得当作公司或岗位失效。
3. 职责完整、届别/方向符合且仍在招的岗位进入下方统一过滤与去重流程；没有匹配岗位的公司只留在独立观察池，不进入岗位主表。
4. 将合并后的公司数组写到 `/tmp/high-growth-company-leads.json`，再运行：

```
python3 $SKILL_DIR/scripts/update_company_watchlist.py \
  --input /tmp/high-growth-company-leads.json \
  --state $SKILL_DIR/state/high-growth-company-watchlist.json \
  --output $SKILL_DIR/../../output/high-growth-company-watchlist-current.json \
  --date $(date +%F)
```

即使本轮没有新公司，也要用空数组运行一次，以刷新结构并在日报中报告零新增。

### 3. 合并 + 过滤

把 4 份结构化列表合并成一个数组。读 `$SKILL_DIR/references/keyword-filters.md` 了解过滤逻辑，按 `config.json` 的 `job_filter` 字段执行：
- 命中 `positive_keywords` 任一 → 保留。
- 命中 `fuzzy_keywords`、但未注明具体方向 → 保留，标题末尾加 `[方向待确认]`。
- 命中 `intern_exclusion_keywords`（含"实习转正"）→ 排除，无论是否也命中 `formal_recruit_keywords`；**但如果 `config.json` 的 `include_internships` 为 `true`，这一条整体跳过，实习岗位正常保留**。
- 明确写出早于 `target_grad_year` 的届别 → 排除。
- 其余按 `references/keyword-filters.md` 中的规则处理。
- 地域不过滤，`city` 字段照抄原文。
- 职责缺失的记录不进入主表。每条主表记录还必须维护 `grad_target`、`recruitment_track`、`is_2027_campus`、`enterprise_type`、`is_central_state_owned`、`watch_priority`、`match_level` 和 `verification`。

把过滤后的候选列表写成 JSON 数组文件，例如 `/tmp/autumn-recruitment-candidates.json`（字段同上）。

### 4. 去重

去重前完成官网链接选择，并保留 `discovery_url` / `discovery_platform` 作为牛客原始来源证据。同一已见岗位从牛客升级为官网链接时，按原始发现链接确认记录身份，更新状态键和当前候选中的对应记录，保留 `first_seen` 及已有处理状态，不计入新增。共享一个官网校招入口的不同岗位不能只按 URL 合并。若另有本地去重实现，也必须遵循相同语义。

运行：

```
python3 $SKILL_DIR/scripts/dedupe.py \
  --input /tmp/autumn-recruitment-candidates.json \
  --state $SKILL_DIR/state/seen_postings.json \
  --config $SKILL_DIR/config.json \
  --output /tmp/autumn-recruitment-new-only.json
```

这一步会原地更新 `state/seen_postings.json`（新岗位写入、已见岗位刷新 `last_confirmed`、过季自动归档），保留职责和上述标注字段，并把真正新增的岗位输出到 `--output` 指定的文件。对当前候选列表和状态文件运行 `annotate.py` 可回填历史记录的标注字段。

### 5. 核实新公司（可选，有上限）

本步仅是其他来源的补充核实；牛客岗位的官网优先核实已在发现/存量复核阶段强制执行，不受“新公司”或“最多 5 家”的限制。

在 `/tmp/autumn-recruitment-new-only.json` 中，找出"公司此前从未出现过"的记录（即该公司在 `state/seen_postings.json` 里除了这条新记录外没有其他历史岗位）。最多取 5 家这样的新公司，为每家发起一个子 agent（同样要求"必须加载 web-access skill 并遵循指引"，目标是"在该公司官方校园招聘官网核实这个岗位是否存在，若存在返回权威链接"）。

若核实到官方链接，同步更新当前候选、`/tmp/autumn-recruitment-new-only.json` 和 `state/seen_postings.json` 中对应记录的 `source_url`/`source_platform` 字段，并重算状态键；保留原始发现链接。若核实过程中发现该岗位实际届别不符合目标届别（例如页面明确写着更早的届别），应从对应输出和状态中移除该记录，不计入本次新增。核实失败或该公司超过本步上限的其他来源记录，保留原聚合帖链接；牛客记录仍按强制规则记录具体回退原因。

### 6. 输出候选结果（通用层）

将当前有效候选列表和本轮新增列表保存为 JSON。需要表格、数据库或其他界面时，由使用方提供独立的输出适配器；适配器不得改变岗位过滤、去重、来源核验和状态语义。通用 skill 不保存个人投递状态、简历材料或账号信息。

如果使用方配置了自己的表格导出适配器，导出后应检查岗位链接、职责、来源证据和标注字段完整；导出失败不得回滚 JSON 和状态更新，应在日报中说明并留待下次重试。

### 7. 渲染日报

```
python3 $SKILL_DIR/scripts/digest.py render \
  --new /tmp/autumn-recruitment-new-only.json \
  --state $SKILL_DIR/state/seen_postings.json \
  --config $SKILL_DIR/config.json \
  --company-watch $SKILL_DIR/../../output/high-growth-company-watchlist-current.json \
  --date $(date +%F) > /tmp/autumn-recruitment-digest.md
```

### 8. 输出最终回复

最终回复内容 = `/tmp/autumn-recruitment-digest.md` 的完整内容，原样输出即可，不需要额外包装。

无论有没有新增岗位，都必须正常输出一份日报（`digest.py render` 已经处理了"无新增"分支），至少报告新增岗位数、删除过期岗位数、当前有效岗位总数、广州/深圳优先岗位摘要和高成长公司增量层覆盖情况，不要空手结束任务。来源覆盖 JSON 也必须单列高成长公司发现、深入复核、匹配岗位、暂无岗位、职责不完整、访问受限和暂停关注数量。
