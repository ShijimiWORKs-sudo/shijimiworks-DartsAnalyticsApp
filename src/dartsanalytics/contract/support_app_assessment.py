"""DartsSupportApp `ai_form_assessments` extension-point export
(docs §11「DartsSupportAppとの位置付け」の統合方針4択 — ユーザーが
2026-09-17に選択した選択肢4「DartsSupportApp側のOpenAI API連携の拡張
ポイントを使う」に対応する、DartsAnalyticsApp側のエクスポート実装)。

## 背景（docs/reports/release/darts-support-schema-diff.md参照）

`shijimiworks-DartsSupportApp`の`docs/IMPLEMENTATION_NOTES.md`
「OpenAI API 連携の拡張ポイント」節（読み取り専用clone、書き込み・push
は一切行っていない）に、以下の3点が明記されている：

    - `src/domain/assessment.ts` の prompt 生成と parser は API 連携時にも
      再利用できます。
    - `ai_form_assessments.source_type` 相当の列追加で `manual_clipboard`
      と `openai_api` を分離できます。
    - API 応答保存時も raw text、parsed JSON、raw hash を維持し、既存の
      重複防止と改善管理に接続します。

ユーザーは4択のうち「4. DartsSupportApp側のOpenAI API連携の拡張ポイント
を使い、DartsAnalyticsAppの解析結果をai_form_assessmentsの
source_type='darts_analytics_app'のような形で流し込む」を選んだ
（本モジュール新設のコミットメッセージ参照）。

## このモジュールが実際に行うこと・行わないこと

**行うこと**：DartsAnalyticsAppの`IntegratedAnalysisReport`/
`AdvisorOutput`を、DartsSupportApp既存の`ai_form_assessments`テーブルの
列（`raw_text`/`raw_hash`/`parsed_json`/`parse_status`/
`recognized_heading_count`）に一致する形へ変換するドラフトを生成する。
`raw_text`は、DartsSupportApp既存の`assessmentHeadingMap`
（15見出し：総合評価/良かった点/改善が必要な点/スタンス/構え/
テイクバック/リリース/フォロースルー/頭・肩・肘の動き/3投の再現性/
前回評価から改善した点/まだ改善していない点/次回、最優先で意識すること/
おすすめ練習メニュー/評価の確信度）をそのまま流用して組み立てる —
これにより、DartsSupportApp側は**そのコードを一切変更せずに**、既存の
`parseChatGptAssessment()`で理論上パース可能な形式になる（実際の
DartsSupportApp DBへの書き込み・importコード自体はこのセッションでは
実装・実行していない — 別リポジトリへの書き込みは指示書§14「破壊的変更に
ユーザー確認が必要」の対象であり、DartsAnalyticsApp側のエクスポート形式を
用意するところまでに留める）。

`raw_hash`は、DartsSupportApp既存の`hashAssessmentRawText()`
（FNV-1a風32bitハッシュ、UTF-16コード単位ベース）をPythonに移植した
ものを使用し、同一テキストに対して同じハッシュ値になるようにしている
（`ai_form_assessments`の`UNIQUE(practice_session_id, raw_hash)`制約に
噛み合わせるため）。

**行わないこと（重要な既知の制約）**：`source_type`列は、2026-09-17時点で
DartsSupportApp実リポジトリの`src/db/schema.ts`を確認した限り**まだ
実装されていない**（IMPLEMENTATION_NOTESに「列追加で分離できる」と
書かれているだけで、実際のCREATE TABLE文には存在しない）。したがって
`source_type='darts_analytics_app'`は、DartsSupportApp側がこの拡張
ポイントを実装した将来のために**先行して用意した提案値**であり、現状の
実スキーマに書き込み可能な列ではない。DartsSupportApp側のマイグレーション
実装・実際のDBへのimport処理は、このリポジトリのスコープ外（別アプリへの
書き込みであり、指示書§11/§14の停止条件に該当するため、ユーザーから
DartsSupportApp側での作業の明示的な依頼があるまで着手しない）。

## フィールド対応方針（IntegratedAnalysisReport/AdvisorOutput → 15見出し）

現時点でDartsAnalyticsApp内部に実装されている解析結果のみを使い、
存在しないデータは「未登録」（DartsSupportApp自身のChatGPTプロンプトが
指示する既存の慣習と同一の文言）、姿勢推定カテゴリ（スタンス/構え/
テイクバック/リリース/フォロースルー/頭・肩・肘の動き）はPhase 5の
Pose特徴量が本レポートに未結線（release-readiness.md 未解決事項8参照）
のため「映像では判断できない」（同じくDartsSupportApp自身のプロンプトの
既存文言）で埋める。仮説・提案は`AdvisorOutput`の`Hypothesis`/
`RecommendedTest`をそのまま使い、断定的な表現への書き換えは一切行わない
（AGENTS.md §2を維持）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dartsanalytics.advisor.models import AdvisorOutput
from dartsanalytics.common.confidence import confidence_level
from dartsanalytics.integrated.report import IntegratedAnalysisReport

# DartsSupportApp src/domain/assessment.ts の assessmentHeadingMap をそのまま
# 転記したもの（読み取り専用clone、2026-09-17時点）。キー・見出し文言・
# 順序のいずれも変更しない — 一致していることが、DartsSupportApp既存の
# parseChatGptAssessment()での理論上のパース可能性の前提になる。
ASSESSMENT_HEADING_MAP: dict[str, str] = {
    "overall": "総合評価",
    "goodPoints": "良かった点",
    "improvementPoints": "改善が必要な点",
    "stance": "スタンス",
    "setup": "構え",
    "takeback": "テイクバック",
    "release": "リリース",
    "followThrough": "フォロースルー",
    "headShoulderElbow": "頭・肩・肘の動き",
    "threeThrowReproducibility": "3投の再現性",
    "improvedSincePrevious": "前回評価から改善した点",
    "notImprovedYet": "まだ改善していない点",
    "nextPriority": "次回、最優先で意識すること",
    "recommendedPractice": "おすすめ練習メニュー",
    "confidence": "評価の確信度",
}

# DartsSupportApp自身のChatGPTプロンプト（generateChatGptPrompt）が使う
# 既存の文言をそのまま流用（未登録データ／映像から判断できないデータの
# 表現を独自に発明しない）。
NOT_REGISTERED = "未登録"
CANNOT_JUDGE_FROM_VIDEO = "映像では判断できない"

# 「4択」のうちユーザーが選んだ選択肢4に対応する提案値。DartsSupportApp
# 実スキーマにはまだ存在しない列の値である点に注意（モジュールdocstring
# 参照）。
PROPOSED_SOURCE_TYPE = "darts_analytics_app"

# DartsSupportApp memoryRepository.ts/repository.ts が実際に使っている
# parse_status の値（'parsed' | 'raw_only' | 'duplicate'）のうち、本モジュール
# は常に全15見出しを出力するため 'parsed' 固定でよい（hasRecognizedHeading
# は常にtrueになる）。
PARSE_STATUS_PARSED = "parsed"

# 次回最優先事項として提示するRecommendedTestの最大件数。DartsSupportApp
# 自身のプロンプト文言「一度に多くの修正を求めず、次回の練習で意識する
# 改善点は最大2点に絞ってください」に合わせた（このアプリ側の判断ではなく、
# 連携先の既存の設計方針をそのまま踏襲）。
MAX_NEXT_PRIORITY_ITEMS = 2


def _hash_assessment_raw_text(raw_text: str) -> str:
    """DartsSupportApp `src/domain/assessment.ts` の
    `hashAssessmentRawText()`（FNV-1a風32bitハッシュ、UTF-16コード単位
    ベース）のPython移植。`ai_form_assessments`の
    `UNIQUE(practice_session_id, raw_hash)`制約と噛み合わせるために、
    同一テキストに対して同じ値を返す必要がある。

    既知の制約：JSの`charCodeAt`はUTF-16コード単位を1つずつ処理するため、
    BMP外の文字（一部の絵文字・拡張漢字）はサロゲートペアとして2回処理
    される。Pythonの`for ch in str`はコードポイント単位で処理するため、
    BMP外の文字を含むテキストでは異なるハッシュ値になりうる。本モジュール
    が生成するテキスト（本アプリの解析結果・日本語の定型文）にはBMP外の
    文字は含まれないため、実用上の差異は生じない。
    """
    h = 2166136261
    for ch in raw_text:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return format(h, "08x")


@dataclass(frozen=True)
class SupportAppAssessmentDraft:
    """DartsSupportApp `ai_form_assessments`の列に対応するドラフト。

    `source_type`は実スキーマにまだ存在しない列の提案値（モジュール
    docstring参照）。`account_id`/`player_id`/`practice_session_id`は、
    darts-support-schema-diff.mdが明らかにした通りDartsAnalyticsApp内部の
    IDとDartsSupportApp側のIDは別空間のため、呼び出し側が
    DartsSupportApp側の実IDを把握している場合のみ明示的に渡す
    （デフォルトNone、本アプリ内部のsession_id等を自動で流用しない —
    contract/support_app.py の設計方針と同じ）。
    """

    raw_text: str
    raw_hash: str
    parsed_json: dict[str, str]
    parse_status: str
    recognized_heading_count: int
    source_type: str = PROPOSED_SOURCE_TYPE
    account_id: str | None = None
    player_id: str | None = None
    practice_session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "player_id": self.player_id,
            "practice_session_id": self.practice_session_id,
            "raw_text": self.raw_text,
            "raw_hash": self.raw_hash,
            "parsed_json": dict(self.parsed_json),
            "parse_status": self.parse_status,
            "recognized_heading_count": self.recognized_heading_count,
            "source_type": self.source_type,
        }


def _format_hypotheses(hypotheses: list) -> str:
    if not hypotheses:
        return NOT_REGISTERED
    lines = []
    for h in hypotheses:
        level = confidence_level(h.confidence).value
        lines.append(f"・{h.category}：{h.description}（確信度: {level}, {h.confidence:.2f}）")
    return "\n".join(lines)


def _format_next_priority(recommended_tests: list) -> str:
    if not recommended_tests:
        return NOT_REGISTERED
    ordered = sorted(recommended_tests, key=lambda t: t.confidence, reverse=True)
    top = ordered[:MAX_NEXT_PRIORITY_ITEMS]
    lines = []
    for t in top:
        lines.append(f"・{t.related_category}：{t.description}")
        if t.expected_effect:
            lines.append(f"  期待される効果（仮説段階、保証ではない）：{t.expected_effect}")
    return "\n".join(lines)


def _format_recommended_practice(recommended_tests: list) -> str:
    if not recommended_tests:
        return NOT_REGISTERED
    lines = []
    for t in recommended_tests:
        lines.append(f"・{t.measurement_plan}（判定基準：{t.decision_criteria}）")
    return "\n".join(lines)


def _format_overall(report: IntegratedAnalysisReport) -> str:
    parts = []
    if report.dispersion is not None:
        d = report.dispersion
        parts.append(
            f"BULL的中率 {d.bull_rate:.1%}、グルーピング中心からの平均距離 "
            f"{d.mean_center_distance:.3f}（正規化座標）。"
        )
    if report.frequent_segments is not None:
        counts = report.frequent_segments.segment_counts
        if counts:
            top = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:3]
            top_str = ", ".join(f"{segment}×{count}" for segment, count in top)
            parts.append(f"頻出セグメント: {top_str}。")
    if not parts:
        return NOT_REGISTERED
    return " ".join(parts)


def build_support_app_assessment_draft(
    report: IntegratedAnalysisReport,
    advisor_output: AdvisorOutput,
    *,
    account_id: str | None = None,
    player_id: str | None = None,
    practice_session_id: str | None = None,
    improved_since_previous: str | None = None,
    not_improved_yet: str | None = None,
) -> SupportAppAssessmentDraft:
    """`IntegratedAnalysisReport`/`AdvisorOutput`から
    `SupportAppAssessmentDraft`を組み立てる。

    `improved_since_previous`/`not_improved_yet`は、学習ログ
    （dartsanalytics.learning_log、docs §9）に対応する介入履歴の要約が
    あれば呼び出し側から渡す（このモジュール単体では複数セッションに
    またがる「前回からの変化」を知りようがないため、生成しない）。
    省略時は「未登録」。
    """
    if report.session_id != advisor_output.session_id:
        raise ValueError(
            f"report.session_id ({report.session_id!r}) does not match "
            f"advisor_output.session_id ({advisor_output.session_id!r})"
        )

    sections: dict[str, str] = {
        "overall": _format_overall(report),
        "goodPoints": NOT_REGISTERED,
        "improvementPoints": _format_hypotheses(advisor_output.hypotheses),
        "stance": CANNOT_JUDGE_FROM_VIDEO,
        "setup": CANNOT_JUDGE_FROM_VIDEO,
        "takeback": CANNOT_JUDGE_FROM_VIDEO,
        "release": CANNOT_JUDGE_FROM_VIDEO,
        "followThrough": CANNOT_JUDGE_FROM_VIDEO,
        "headShoulderElbow": CANNOT_JUDGE_FROM_VIDEO,
        "threeThrowReproducibility": NOT_REGISTERED,
        "improvedSincePrevious": improved_since_previous or NOT_REGISTERED,
        "notImprovedYet": not_improved_yet or NOT_REGISTERED,
        "nextPriority": _format_next_priority(advisor_output.recommended_tests),
        "recommendedPractice": _format_recommended_practice(advisor_output.recommended_tests),
        "confidence": _format_confidence(advisor_output),
    }

    lines: list[str] = []
    for key, heading in ASSESSMENT_HEADING_MAP.items():
        lines.append(f"【{heading}】")
        lines.append(sections[key])
        lines.append("")
    raw_text = "\n".join(lines).rstrip() + "\n"

    return SupportAppAssessmentDraft(
        raw_text=raw_text,
        raw_hash=_hash_assessment_raw_text(raw_text),
        parsed_json=sections,
        parse_status=PARSE_STATUS_PARSED,
        recognized_heading_count=len(ASSESSMENT_HEADING_MAP),
        account_id=account_id,
        player_id=player_id,
        practice_session_id=practice_session_id,
    )


def _format_confidence(advisor_output: AdvisorOutput) -> str:
    values = [h.confidence for h in advisor_output.hypotheses] + [
        t.confidence for t in advisor_output.recommended_tests
    ]
    if not values:
        return NOT_REGISTERED
    avg = sum(values) / len(values)
    level = confidence_level(avg).value
    return (
        f"本アプリの解析に基づく仮説・提案の平均確信度: {level}（{avg:.2f}）。"
        "DartsAnalyticsApp独自の確信度基準（docs §23）によるものであり、"
        "ChatGPTによる主観評価とは算出方法が異なる。"
    )
