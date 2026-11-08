"""P1-5 验证 v3：完整验证 CRUD 工具（dispatch + TOOLS 注册 + 直接调用）。"""
import sys
sys.path.insert(0, 'flybrain-connectome-mcp/mcp_connectome')
import server

crud_tool_names = ['list_crud_units', 'get_crud_unit', 'add_crud_unit',
                   'update_crud_unit', 'delete_crud_unit']

# 1. TOOLS 注册
registered = [t['name'] for t in server.TOOLS if t['name'] in crud_tool_names]
assert set(registered) == set(crud_tool_names), f'TOOLS 注册不完整: {registered}'
print('TOOLS 注册: OK —', registered)
print('Total tools:', len(server.TOOLS))

# 2. handle_call dispatch（read-only 验证）
r = server.handle_call('list_crud_units', {})
print('list_crud_units:', str(r)[:60])

# 3. 验证每个 CRUD 工具的 inputSchema 完整
for t in server.TOOLS:
    if t['name'] in crud_tool_names:
        assert t.get('description'), f"{t['name']} 缺 description"
        assert 'inputSchema' in t, f"{t['name']} 缺 inputSchema"
print('CRUD tools schema: OK')
