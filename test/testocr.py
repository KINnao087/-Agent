import os

from paddleocr import PaddleOCR

ocr = PaddleOCR(
    lang="ch",  # 中文
    device="gpu",
    use_doc_orientation_classify=False,  # 不做整页方向分类
    use_doc_unwarping=False,  # 不做文档矫正
    use_textline_orientation=False,  # 不做单行方向分类
)

results = ocr.predict(r"./test.png")

for i, res in enumerate(results, start=1):
  data = res.json["res"]

  print(f"=== page {i} ===")
  texts = data["rec_texts"]
  scores = data["rec_scores"]
  boxes = data["rec_boxes"]

  for text, score, box in zip(texts, scores, boxes):
      print(f"{score:.3f} | {text} | {box}")

  # 保存可视化结果图
  res.save_to_img("./output")
  # 保存 JSON 结果
  res.save_to_json("./output")
