#!/usr/bin/env python3
"""
process_data.py - 학원 원본 데이터를 Jekyll 페이지용 JSON으로 가공 (Option-B: 동 단위로 묶어서
그 안에 학원 카드 여러 개를 나열 - 13만개가 넘어 개별 페이지는 불가능, wooapay와 동일 패턴)

입력: _rawdata/academy_raw.json (138,568건)
출력: _rawdata/leaf_{시도}.json  - 시도별 분할, 시군구>동 계층 구조로 그룹핑된 원본
      search_index.json          - 검색용 경량 인덱스 (전체 학원)
"""
import json, re, sys
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
RAW = ROOT / "_rawdata" / "academy_raw.json"
RAWDATA_DIR = ROOT / "_rawdata"
SEARCH_INDEX_OUT = ROOT / "search_index.json"

# 교육청 명칭 변경 이력 때문에 지역별로 신/구 명칭이 섞여서 나타남
# (예: 광주는 "광주광역시교육청"과 "전남광주통합특별시교육청(광주)"가 둘 다 존재) -
# 실제 원본 데이터에서 나타나는 값 전부를 직접 매핑해 대응.
DO_MAP = {
    "서울특별시교육청": "서울", "부산광역시교육청": "부산", "대구광역시교육청": "대구",
    "인천광역시교육청": "인천", "대전광역시교육청": "대전", "울산광역시교육청": "울산",
    "세종특별자치시교육청": "세종", "경기도교육청": "경기",
    "강원특별자치도교육청": "강원", "강원도교육청": "강원",
    "충청북도교육청": "충북", "충청남도교육청": "충남",
    "전북특별자치도교육청": "전북", "전라북도교육청": "전북",
    "전라남도교육청": "전남", "전남광주통합특별시교육청(전남)": "전남",
    "광주광역시교육청": "광주", "전남광주통합특별시교육청(광주)": "광주",
    "경상북도교육청": "경북", "경상남도교육청": "경남",
    "제주특별자치도교육청": "제주",
}


def guess_sido(atpt_nm):
    text = (atpt_nm or "").strip()
    return DO_MAP.get(text, "")


def guess_dong(addr):
    """도로명주소 3번째 토큰에서 읍/면/구를 추출 (동은 도로명주소 체계상 대부분 생략되어
    나타나지 않음 - 실측 결과 읍/면 지역만 3번째 토큰에 남아있고, 구가 있는 시는 구까지만
    나옴). 그마저도 없으면(강남구처럼 이미 자치구가 sigungu인 경우 등) "기타"로 묶은 뒤
    아래 chunk_oversized_leaves()에서 인원수 기준으로 다시 잘게 쪼갠다."""
    if not addr:
        return "기타"
    parts = addr.strip().split()
    if len(parts) >= 3 and re.search(r"(읍|면|구)$", parts[2]):
        return parts[2]
    return "기타"


LEAF_CAP = 300  # 리프 하나에 들어갈 최대 학원 수 (넘으면 번호 붙여 분할)


def chunk_oversized_leaves(items):
    """(시도,시군구,동) 리프가 LEAF_CAP을 넘으면 이름순 정렬 후 순번으로 잘라
    "동-2", "동-3"처럼 분할한다. 매 빌드마다 정렬 기준이 같아 분할 결과가 안정적으로 유지됨."""
    groups = defaultdict(list)
    for it in items:
        groups[(it["doShort"], it["sigungu"], it["dong"])].append(it)

    for key, group in groups.items():
        if len(group) <= LEAF_CAP:
            continue
        group.sort(key=lambda x: x["name"])
        do, sg, dong = key
        for i in range(0, len(group), LEAF_CAP):
            chunk_no = i // LEAF_CAP + 1
            if chunk_no == 1:
                continue  # 첫 청크는 원래 동 이름 유지
            for it in group[i:i + LEAF_CAP]:
                it["dong"] = f"{dong}-{chunk_no}"
    return items


def clean(v):
    if v is None:
        return ""
    v = str(v).strip()
    return "" if v.lower() == "null" else v


def main():
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    print(f"원본 {len(raw)}건")

    items = []
    skipped_status = 0
    skipped_region = 0
    for d in raw:
        if clean(d.get("REG_STTUS_NM")) != "개원":
            skipped_status += 1
            continue
        do_short = guess_sido(d.get("ATPT_OFCDC_SC_NM"))
        sigungu = clean(d.get("ADMST_ZONE_NM")) or "기타"
        if not do_short:
            skipped_region += 1
            continue
        addr = clean(d.get("FA_RDNMA"))
        dong = guess_dong(addr)

        # ACA_ASNUM은 교육청별로 독립 채번되어 전국 기준으로는 중복될 수 있어
        # 교육청코드를 붙여 전역 유일 id로 사용 (실측: 138,568건 중 29,661개 번호가 중복 발견됨)
        office_code = clean(d.get("ATPT_OFCDC_SC_CODE"))
        items.append({
            "id": f"{office_code}-{clean(d.get('ACA_ASNUM'))}",
            "name": clean(d.get("ACA_NM")),
            "kind": clean(d.get("ACA_INSTI_SC_NM")),
            "doShort": do_short,
            "sigungu": sigungu,
            "dong": dong,
            "realm": clean(d.get("REALM_SC_NM")),
            "course": clean(d.get("LE_CRSE_NM")),
            "fee": clean(d.get("PSNBY_THCC_CNTNT")),
            "capacity": d.get("DTM_RCPTN_ABLTY_NMPR_SMTOT"),
            "addr": addr,
            "addrDetail": clean(d.get("FA_RDNDA")),
            "tel": clean(d.get("FA_TELNO")),
            "estYmd": clean(d.get("ESTBL_YMD")),
        })

    print(f"제외: 비활성상태 {skipped_status}건, 지역인식실패 {skipped_region}건")
    print(f"유효 {len(items)}건")

    # id 기준 중복 제거 (혹시 페이지네이션 중복 있을 경우 대비)
    seen_ids = set()
    dedup = []
    for it in items:
        key = it["id"] or f"{it['name']}|{it['addr']}"
        if key in seen_ids:
            continue
        seen_ids.add(key)
        dedup.append(it)
    print(f"중복제거 후: {len(dedup)}건")
    items = dedup

    items = chunk_oversized_leaves(items)

    by_do = defaultdict(list)
    for it in items:
        by_do[it["doShort"]].append(it)

    RAWDATA_DIR.mkdir(parents=True, exist_ok=True)
    for do, group in by_do.items():
        out = RAWDATA_DIR / f"leaf_{do}.json"
        out.write_text(json.dumps(group, ensure_ascii=False), encoding="utf-8")
        size_mb = out.stat().st_size / 1024 / 1024
        print(f"  {do}: {len(group)}건 -> {out.name} ({size_mb:.1f}MB)")

    do_counts = Counter(it["doShort"] for it in items)
    print("\n지역별 학원 수:")
    for do, cnt in sorted(do_counts.items(), key=lambda x: -x[1]):
        print(f"  {do}: {cnt}개")

    # 동 단위 리프 개수/크기 분포 확인
    leaf_counter = Counter((it["doShort"], it["sigungu"], it["dong"]) for it in items)
    vals = list(leaf_counter.values())
    print(f"\n리프(동) 개수: {len(leaf_counter)}개, 평균 {sum(vals)/len(vals):.1f}건/리프, 최대 {max(vals)}건")

    # 검색 인덱스: 전체, 경량 필드만 (동 페이지로 연결 + 앵커)
    index = [
        {"n": it["name"], "do": it["doShort"], "sg": it["sigungu"], "dg": it["dong"], "id": it["id"], "k": it["kind"]}
        for it in items
    ]
    SEARCH_INDEX_OUT.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size_mb = SEARCH_INDEX_OUT.stat().st_size / 1024 / 1024
    print(f"\n검색 인덱스 {len(index)}개 저장 -> {SEARCH_INDEX_OUT} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
