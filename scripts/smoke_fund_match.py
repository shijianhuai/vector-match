"""端到端冒烟：灌入示例基金数据，验证三种检索模式。

用法：先启动服务（docker compose up -d），再执行 python scripts/smoke_fund_match.py
环境变量：BASE_URL（默认 http://localhost:8000）、
         SMOKE_USERNAME / SMOKE_PASSWORD（默认 admin / admin123；账号不存在时自动注册）
"""

import os
import sys
import time

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
USERNAME = os.environ.get("SMOKE_USERNAME", "admin")
PASSWORD = os.environ.get("SMOKE_PASSWORD", "admin123")

FUNDS = [
    {"q": "易方达蓝筹精选混合", "a": "005827", "indexes": [{"text": "易方达蓝筹"}]},
    {"q": "中欧医疗健康混合A", "a": "003095", "indexes": [{"text": "中欧医疗"}]},
    {"q": "招商中证白酒指数A", "a": "161725", "indexes": [{"text": "招商白酒"}]},
    {"q": "华夏上证50ETF联接A", "a": "001051", "indexes": [{"text": "上证50"}]},
    {"q": "景顺长城新兴成长混合A", "a": "260108", "indexes": [{"text": "景顺成长"}]},
    {"q": "富国天惠成长混合A", "a": "161005", "indexes": [{"text": "富国天惠"}]},
]


def get_token(client: httpx.Client) -> str:
    resp = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    if resp.status_code == 401:
        # 账号不存在时自动注册后登录
        client.post("/api/auth/register", json={"username": USERNAME, "password": PASSWORD}).raise_for_status()
        resp = client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    resp.raise_for_status()
    return resp.json()["token"]


def main() -> int:
    with httpx.Client(base_url=BASE_URL, timeout=30) as auth_client:
        token = get_token(auth_client)
    client = httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}, timeout=30)

    ds = client.post("/api/core/dataset/create", json={"name": f"smoke-基金库-{int(time.time())}"}).json()
    dataset_id = ds["id"]
    col = client.post(
        "/api/core/dataset/collection/create",
        json={"datasetId": dataset_id, "name": "smoke集", "type": "virtual"},
    ).json()
    collection_id = col["id"]
    resp = client.post(
        "/api/core/dataset/data/pushData", json={"collectionId": collection_id, "data": FUNDS}
    )
    assert resp.status_code == 200 and resp.json()["insertLen"] == len(FUNDS), resp.text
    print(f"已推送 {len(FUNDS)} 条数据，等待训练...")

    deadline = time.time() + 120
    while time.time() < deadline:
        body = client.get(
            "/api/core/dataset/data/list", params={"collectionId": collection_id, "pageSize": 50}
        ).json()
        if body["total"] == len(FUNDS) and all(item["trained"] for item in body["list"]):
            break
        time.sleep(2)
    else:
        print("FAIL 训练超时（120s）")
        return 1
    print("训练完成，开始检索验证")

    cases = [
        ("语义检索「易方达蓝筹」", {"datasetId": dataset_id, "text": "易方达蓝筹", "searchMode": "embedding"}, "005827"),
        ("全文检索「005827」", {"datasetId": dataset_id, "text": "005827", "searchMode": "fullTextRecall"}, "005827"),
        ("混合+重排「医疗基金」", {"datasetId": dataset_id, "text": "医疗基金", "searchMode": "mixedRecall", "usingReRank": True}, "003095"),
    ]
    ok = True
    for title, payload, expect_code in cases:
        hits = client.post("/api/core/dataset/search", json=payload).json()
        top = hits[0] if hits else None
        passed = top is not None and top["a"] == expect_code
        ok = ok and passed
        if top:
            print(f"{'PASS' if passed else 'FAIL'} {title} -> {top['q']} ({top['a']}) score={top['score']:.4f}")
        else:
            print(f"FAIL {title} -> 无结果")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
