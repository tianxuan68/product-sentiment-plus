import json
import csv


def jsonl_to_csv(jsonl_file, csv_file):

    with open(jsonl_file, "r", encoding="utf-8") as f:
        first_line = json.loads(next(f))


    # 获取字段名
    fields = first_line.keys()


    with open(
        csv_file,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as out:

        writer = csv.DictWriter(
            out,
            fieldnames=fields
        )

        writer.writeheader()


        # 写第一条
        writer.writerow(first_line)


        # 写剩余数据
        with open(
            jsonl_file,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:
                data = json.loads(line)
                writer.writerow(data)


    print("转换完成")


jsonl_to_csv(
    "E:\\tianxuan\\product-sentiment-plus\\product-sentiment-ai\\data\\sources\\Appliances.jsonl",
    "E:\\tianxuan\\product-sentiment-plus\\product-sentiment-ai\\data\\sources\\reviews.csv"
)