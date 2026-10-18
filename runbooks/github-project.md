# GitHub Project 维护

## 入口与组织方式

- Project：[milesprint-issues](https://github.com/users/ceasarXuu/projects/6)，归属 `ceasarXuu`，编号 `6`；沿用参考 Project 的私有可见性。
- 关联仓库：`ceasarXuu/MileSprint`。
- 按“版本 → 主题（feature / fix）→ issue”组织：Milestone 表示已确认版本，父 issue 表示主题，子 issue 表示具体工作，Labels 标记类型。
- 当前已有 [v0.0.1 Milestone](https://github.com/ceasarXuu/MileSprint/milestone/1) 和 [设备管理器主题 issue #1](https://github.com/ceasarXuu/MileSprint/issues/1)，尚无软件实现或正式发布。`docs/releases/v0.0.0` 仅为初始概念归档。

## 视图与状态

| 视图 | 布局 | 筛选与分组 |
| --- | --- | --- |
| [All Issues](https://github.com/users/ceasarXuu/projects/6/views/4) | 总表 | 全部条目，展示 Milestone、Parent issue 和子 issue 进度 |
| [待定需求](https://github.com/users/ceasarXuu/projects/6/views/1) | 看板 | `no:milestone`，按 Status 分列 |
| [版本看板](https://github.com/users/ceasarXuu/projects/6/views/5) | 看板 | 按 Milestone 分组、Status 分列 |
| [主题看板](https://github.com/users/ceasarXuu/projects/6/views/6) | 看板 | 按 Parent issue 分组、Status 分列 |

状态沿用参考 Project：`TODO → In Progress → In Review → Done`，其中 In Review 包括 PR 评审或交付验收。

已复制并启用六项工作流：添加子 issue、自动关闭 issue、添加条目时设置状态、关闭条目时设置状态、关联 PR 时设置状态、合并 PR 时设置状态。

**自动收录新 issue 尚未配置**：复制 Project 不会迁移 Auto-add 工作流，需在 GitHub Project 的 Workflows 中针对本仓库配置。配置前可手动加入，或运行：

```sh
gh project item-add 6 --owner ceasarXuu --url https://github.com/ceasarXuu/MileSprint/issues/实际编号
```

## 已验证的配置经验

- `gh project copy` 可复用视图、字段和状态工作流；仓库关联需另用 `gh project link` 设置。不要复制参考项目的业务条目或沿用其他项目的版本筛选。
- GraphQL `updateProjectV2View` 支持名称、筛选、布局和可见字段；本次查询的 schema 不支持设置分组。需设置分组时可用官方 REST 创建 view。
- REST 路径 `users/{user_id}/projectsV2/{project_number}/views` 的 `user_id` 实测应传用户名 `ceasarXuu`；传数字用户 ID 返回 404。
- REST 的 `visible_fields`、`group_by`、`vertical_group_by` 使用字段的数字 `databaseId`，不是 GraphQL 节点 ID；每次先从目标 Project 查询，不要复用其他 Project 的字段 ID。
- 创建后用 GraphQL 回读 `groupByFields` 与 `verticalGroupByFields` 验证。版本看板应分别返回 Milestone 和 Status，主题看板应分别返回 Parent issue 和 Status。

官方说明：[复制 Project](https://docs.github.com/en/issues/planning-and-tracking-with-projects/creating-projects/copying-an-existing-project)、[创建用户 Project 视图](https://docs.github.com/en/rest/projects/views#create-a-view-for-a-user-owned-project)。
