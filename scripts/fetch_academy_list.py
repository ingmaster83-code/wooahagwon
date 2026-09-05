#!/usr/bin/env python3
"""
fetch_academy_list.py - NEIS 학원교습소정보(acaInsTiInfo) 전량 수집
17개 시도교육청 코드별로 순회하며 페이지네이션 전량 수집 (지역코드 없이는 조회 불가).

출력: _rawdata/academy_raw.json
"""
import json, os, sys, time
import requests

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_rawdata", "academy_raw.json")

API_KEY = os.environ.get("NEIS_API_KEY") or "3d2634b6a79249e4b7a773a27b705cec"
BASE = "https://open.neis.go.kr/hub/acaInsTiInfo"
PAGE_SIZE = 1000

OFFICE_CODES = ["B10", "C10", "D10", "E10", "F10", "G10", "H10", "I10", "J10",
                "K10", "M10", "N10", "P10", "Q10", "R10", "S10", "T10"]


def fetch_page(office_code, page_no, attempt=1):
    params = {
        "KEY": API_KEY, "Type": "json", "pIndex": page_no, "pSize": PAGE_SIZE,
        "ATPT_OFCDC_SC_CODE": office_code,
    }
    try:
        r = requests.get(BASE, params=params, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        if attempt >= 5:
            raise
        print(f"  [재시도 {attempt}] {office_code} page {page_no}: {e}")
        time.sleep(3)
        return fetch_page(office_code, page_no, attempt + 1)


def main():
    all_rows = []
    for office_code in OFFICE_CODES:
        page = 1
        office_total = None
        office_rows = []
        while True:
            data = fetch_page(office_code, page)
            body = data.get("acaInsTiInfo")
            if not body:
                print(f"  {office_code}: 응답 이상 -> {json.dumps(data, ensure_ascii=False)[:200]}")
                break
            head = body[0]["head"]
            if office_total is None:
                office_total = head[0]["list_total_count"]
            rows = body[1]["row"] if len(body) > 1 else []
            if not rows:
                break
            office_rows.extend(rows)
            if len(office_rows) >= office_total:
                break
            page += 1
            if page > 200:
                print(f"  {office_code}: 안전장치 200페이지 초과, 중단")
                break
            time.sleep(0.15)
        all_rows.extend(office_rows)
        print(f"{office_code}: {len(office_rows)} / {office_total}건 (누적 {len(all_rows)})")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False)
    print(f"\n총 {len(all_rows)}건 저장 -> {OUT}")


if __name__ == "__main__":
    main()
