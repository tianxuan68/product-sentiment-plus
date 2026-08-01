import os

# ==================================================
# HuggingFace 新版下载加速
# ==================================================

os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"



import pandas as pd
import torch

from tqdm import tqdm

from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM
)

from huggingface_hub import login



# ==================================================
# 1. HuggingFace Token
# ==================================================

HF_TOKEN = ""


login(
    token=HF_TOKEN
)



# ==================================================
# 2. GPU检查
# ==================================================

print("=" * 50)

if torch.cuda.is_available():

    device = "cuda"

    print(
        "GPU:",
        torch.cuda.get_device_name(0)
    )

else:

    device = "cpu"

    print(
        "当前使用CPU"
    )


print("=" * 50)



# ==================================================
# 3. 加载NLLB翻译模型
# ==================================================

MODEL_NAME = (
    "facebook/nllb-200-distilled-600M"
)



print("正在加载模型...")


tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    token=HF_TOKEN
)



if device == "cuda":


    model = AutoModelForSeq2SeqLM.from_pretrained(
        MODEL_NAME,
        token=HF_TOKEN,
        torch_dtype=torch.float16,
        device_map="auto"
    )


else:


    model = AutoModelForSeq2SeqLM.from_pretrained(
        MODEL_NAME,
        token=HF_TOKEN
    )

    model.to(device)



# 设置源语言：英语

tokenizer.src_lang = "eng_Latn"



print("模型加载完成")



# ==================================================
# 4. 单批翻译函数
# ==================================================

def translate_batch(texts):


    texts = [
        "" if pd.isna(x)
        else str(x)
        for x in texts
    ]


    inputs = tokenizer(

        texts,

        padding=True,

        truncation=True,

        max_length=128,

        return_tensors="pt"

    )



    if device == "cuda":

        inputs = {
            k:v.to(model.device)
            for k,v in inputs.items()
        }



    with torch.no_grad():

        outputs = model.generate(

            **inputs,

            forced_bos_token_id=
            tokenizer.convert_tokens_to_ids(
                "zho_Hans"
            ),

            max_length=128

        )



    results = tokenizer.batch_decode(

        outputs,

        skip_special_tokens=True

    )


    return results





# ==================================================
# 5. 批量处理CSV列
# ==================================================

def translate_column(
        series,
        batch_size=64
):


    texts = (
        series
        .fillna("")
        .tolist()
    )


    results = []



    for i in tqdm(
        range(
            0,
            len(texts),
            batch_size
        )
    ):


        batch = texts[
            i:i+batch_size
        ]


        result = translate_batch(
            batch
        )


        results.extend(
            result
        )



    return results





# ==================================================
# 6. 读取CSV
# ==================================================

INPUT_FILE = (
r"E:\tianxuan\product-sentiment-plus"
r"\product-sentiment-ai\data\sources"
r"\reviews.csv"
)



df = pd.read_csv(
    INPUT_FILE
)



print(
    "原始数据:",
    len(df)
)




# ==================================================
# 7. 随机抽50%
# ==================================================

df = df.sample(
    frac=0.5,
    random_state=42
).reset_index(drop=True)



print(
    "处理数量:",
    len(df)
)




# ==================================================
# 8. 翻译title
# ==================================================

print("\n开始翻译title")


df["title_cn"] = translate_column(

    df["title"],

    batch_size=64

)




# ==================================================
# 9. 翻译text
# ==================================================

print("\n开始翻译text")


df["text_cn"] = translate_column(

    df["text"],

    batch_size=64

)





# ==================================================
# 10. 保存
# ==================================================

OUTPUT_FILE = (
"amazon_reviews_half_cn.csv"
)



df.to_csv(

    OUTPUT_FILE,

    index=False,

    encoding="utf-8-sig"

)



print("=" * 50)

print(
    "翻译完成!"
)

print(
    "输出文件:",
    OUTPUT_FILE
)

print("=" * 50)