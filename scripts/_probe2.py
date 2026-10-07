import sys, json
sys.path.insert(0, r"C:\Users\xing\Desktop\flybrain-connectome")
from scripts.jev_audit_runner import run_batch
out = r"C:\Users\xing\Desktop\flybrain-connectome\scripts\artifacts\jev_audit\cev3_audit.json"
out_txt = r"C:\Users\xing\Desktop\flybrain-connectome\scripts\artifacts\jev_audit\cev3_audit.txt"
qs = [
  {
    "question": "问题: 有没有办法用现有数据严格区分「L1 重建没测到」和「L1 真的没有这条突触」? 如果答「没有」请一句话说明最关键的缺失是什么(不要罗列所有).",
    "mode": "choice",
    "options": ["没有, 现有数据无法区分, 缺单只动物的完整重建/重复测量", "有", "部分有"]
  },
  {
    "question": "问题: 有没有任何 L1 数据点或推理链条能严格支持「这条突触在 L1 存在且是发育新增的(成虫消失)」「这条突触在 L1 不存在但成虫出现」中的至少一种? 请只给最简判定.",
    "mode": "choice",
    "options": ["否, 现有数据不支持这两种严格说法", "是, 支持其中一种", "是, 两种都支持"]
  },
  {
    "question": "问题: 8 个 larv.* 单元的 members 里, 「幼虫重建里实际存在的细胞类型」占比的数值是多少? 若不知道或需要读文件, 请答「需要读文件」.",
    "mode": "noul",
    "polarity": "positive"
  },
  {
    "question": "问题: README 里「MB-FFN 是无标注类」这类把 modality bucket 名字读成注释裁定的表述, 应该: a) 保留(名字即事实) b) 改为「未被 bucket() 识别的模态」(区分测量与裁定) c) 完全删除",
    "mode": "choice",
    "options": ["a", "b", "c"]
  }
]
res = run_batch(qs)
with open(out, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
with open(out_txt, "w", encoding="utf-8") as f:
    for r in res:
        f.write(f"Q: {r['question']}\n  decision: {r['decision']}\n  confidence: {r.get('confidence')}\n  error: {r.get('error')}\n\n")
print("saved")
print(open(out_txt, encoding="utf-8").read())
