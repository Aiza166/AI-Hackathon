# Ground the widow's claim in real rules

> PROTOTYPE research for Coder's Cup 2026. All people, records and services in the build are mock. Every claim below carries a URL. Items marked "unverified" or "(snippet only)" in the research notes keep that marker here and are not presented as fact.

## Summary of decisions for the build team (1 page)

The research supports the team's design, with one forced correction: **the planned rule v2 ("remarried widows keep the pension") has no real-world source, so swap it for the federal 10-year cap on family pension for non-spouse heirs, effective 10 September 2024** ([Business Recorder](https://www.brecorder.com/news/40310086); [Mettis Global](https://mettisglobal.news/govt-fixes-family-pension-at-10-years-after-death/); [The News](https://www.thenews.com.pk/print/1241684-existing-family-pensioners-exempted-from-10-year-limit)). That change is dated, has exact wording and has a grandfather clause, so the Digital Twin can show a real "this would change N past decisions" result. It also leaves Zainab's own claim untouched, because the cap applies only after the spouse dies or becomes ineligible. The other decisions follow.

| # | Decision | Basis |
|---|---|---|
| 1 | Six versioned ZEN rules: spouse first, share split, child age, daughter status, required documents, single pension. v1 to v2 = the 10-year cap (2024-09-10), with existing pensioners exempt. | Sections 1 and 1.3 |
| 2 | Change three team docs: `01-IDEA.md` step 11, `03-ARCHITECTURE.md` rule 4, `05-DEMO-SCRIPT.md` "Publish rule v2" button. | Section 1.4 |
| 3 | A second wife who appears in the family record is a lawful co-sharer, not a fake heir. "Rukhsana" must stay "not in the family record" to count as a red flag. | Rule 4.10 split ([SHC](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)) |
| 4 | Keep the 48h payout-change hold. Extend it to 4 business days when a red flag fires. Add a Confirmation-of-Payee-style match / close match / no match check before any payout. | SSA, FCA, Pay.UK (section 2) |
| 5 | Scam Shield: content rules (fee, code, link, unverified money promise) outweigh the sender ID. Official short codes such as 8171 are evidence, never proof. | BISP, PTA, PSCA (section 2) |
| 6 | Name matching: normalise, block, score with Fellegi-Sunter weights. **No auto-match without exact CNIC.** Choose the threshold on a synthetic set where the false-match rate on hard negatives is 0. | Section 3 |
| 7 | Document checks are a list of risk indicators: OCR cross-check, copy-move on seals, ELA, EXIF context, optional QR decode. **Never show "QR verified"**: no primary source confirms that death certificates carry a QR. | Section 4 |
| 8 | Citizen shell at most 170 KB, with pre-generated ur-PK Azure audio. The outbox flushes on app open and on the `online` event, not only through Background Sync. Server idempotency key per IETF draft. | Section 5 |
| 9 | Jev answers small questions only. Use Choice plus a companion Noul for routing, closed-set Choices with `unreadable` for fields, and Box always paired with a presence Noul. Jev is not a tamper detector. | Section 6 |
| 10 | Scope stays at the full 3-4 person plan. | Section 7 |

---

## 1. Pakistan family pension rules fit six JSON rules and one dated change

Provincial pension rules are quoted in full in a 2025 Sindh High Court order, and they give a clear order of entitlement. The widow of a male servant comes first ([SHC Sukkur C.P. D-198/2025](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)). With several widows, **if widows plus eligible children "does not exceed 4", the pension is divided equally; otherwise "each surviving widow shall get 1/4th of the pension and the balance (if any) shall be divided equally among the surviving eligible children"** ([SHC](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)). The quoted text is internally inconsistent: it says "does not exceed 4" in one place and "more than 3" in another, so the mock rule should pick one reading and state it. If there is no widow, the pension passes to sons "not above 25 years" and unmarried daughters, then down a fixed list that includes the eldest widowed daughter. A 2016 Sindh amendment gives widowed and divorced daughters the pension "for life or till her re-marriage" ([SHC](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)). The son age limit differs by level: 25 in the quoted Sindh text, and 21 for children in the 2024 federal change ([Mettis Global](https://mettisglobal.news/govt-fixes-family-pension-at-10-years-after-death/)). The federal AGPR wording of the same clauses was not fetched and is assumed similar (unverified).

The required documents are consistent across sources: death certificate, claimant CNIC, NADRA FRC, nikah nama for a widow, and a bank account in the claimant's own name ([LegalPK](https://legalpk.com/blog-post/eobi-pension-claim-process-pakistan)). The EOBI survivor form asks for a death certificate "issued by Municipality", an indemnity bond, and a nikah nama attested by a Grade-17 officer ([EOBI survivor form](http://www.eobi.gov.pk/announcement/Pension-Account/Survivor-form.pdf); [PASSCO widow form](https://www.passco.gov.pk/wp-content/uploads/2023/11/Widow-Pension-Form.pdf)). A person may draw only one family pension, but a spouse's own pay or pension does not bar it ([Business Recorder](https://www.brecorder.com/news/40310086)). No source gives the ordinary family pension rate (for example 75% or 100% of the deceased's pension), so that is unverified. The mock should use a made-up amount and label it.

### 1.1 EOBI is a second, simpler scheme

EOBI lists a survivor's pension with "Minimum RS. 10,000/=. Maximum As Per Formula" (snippet; page unreachable) ([EOBI](http://www.eobi.gov.pk/introduction/Pension.html)). Secondary sources say the minimum rose to Rs 11,500 in January 2025 ([GoPunjab](https://gopunjab.pk/eobi-pension/); [LinkedIn](https://www.linkedin.com/pulse/eobi-gratuity-provident-fund-what-every-pakistani-worker-zahid-rulef)). Claims are filed at the regional office of the last workplace, and **date-of-birth mismatch with NADRA is the top cause of rejection** ([LegalPK](https://legalpk.com/blog-post/eobi-pension-claim-process-pakistan)). The survivor contribution minimum in section 22 of the EOBI Act was not verified ([Pakistan Code](https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Nsa-sg-jjjjjjjjjjjjj.html), not fetched).

### 1.2 Six rules, written fresh as ZEN-ready JSON sketches

These are sketches of rule content, not engine syntax. Each rule returns `eligible`, `not_eligible` or `missing_info` plus a reason code. `not_eligible` goes to an officer, never to an automatic rejection.

```json
{
  "ruleset": "survivor-pension",
  "version": "v1",
  "effective_from": "2016-04-07",
  "rules": [
    {"id": "R1_spouse_first", "when": {"relation": "widow", "frc_links_claimant": true, "nikah_nama": "present", "death_verified": true}, "then": "eligible", "basis": "Rule 4.10(2)(A)(i)(a)"},
    {"id": "R2_share_split", "compute": "n = widows + eligible_children; if n <= 4 share = 1/n; else widow_share = 1/4 each, children split remainder", "basis": "Rule 4.10(2)(A)(i)(b)"},
    {"id": "R3_child_age", "when": {"relation": "son", "age_gt": 25, "disabled": false}, "then": "not_eligible", "reason": "CHILD_OVER_AGE"},
    {"id": "R4_daughter_status", "when": {"relation": "daughter", "marital_status_in": ["unmarried", "widowed", "divorced"]}, "then": "eligible_until_remarriage", "note": "divorce date irrelevant (SC 30-07-2025)"},
    {"id": "R5_required_docs", "require": ["death_certificate", "claimant_cnic", "frc", "nikah_nama_if_widow", "bank_title_equals_claimant"], "on_missing": "missing_info", "reason": "ASK_PROOF:<doc>"},
    {"id": "R6_single_pension", "when": {"already_draws_family_pension": true}, "then": "not_eligible", "reason": "SECOND_FAMILY_PENSION"}
  ]
}
```

R4 cites the 2025 Supreme Court ruling, so the strict "v1 as of 2016" label would be anachronistic for that clause. In the demo, set v1's `effective_from` to the date the team chooses and say it is mock.

### 1.3 The real v1 to v2 change: the 10-year cap

**Before (v1):** after the spouse dies or becomes ineligible, remaining family members draw the family pension with no time cap. This is inferred from the change wording; the prior rule text was not fetched (unverified as exact wording).

**After (v2, effective 2024-09-10):** "Ordinary Family Pension, after the death or ineligibility of the spouse, shall be admissible to remaining entitled family members for a maximum period of 10 years". Disabled or special children receive it for life, and entitled children receive it "for 10 years or till the age of 21 years whichever is later" ([Business Recorder, 27-06-2024](https://www.brecorder.com/news/40310086); [Mettis Global, 11-09-2024](https://mettisglobal.news/govt-fixes-family-pension-at-10-years-after-death/)). **The change does not apply to existing family pensioners** ([The News, 19-10-2024](https://www.thenews.com.pk/print/1241684-existing-family-pensioners-exempted-from-10-year-limit)). A Finance Division circular dated 03-01-2025 refers to admissibility for existing family pensioners from 10.09.2024 (snippet only) ([finance.gov.pk](https://www.finance.gov.pk/circulars/circular_03012025.pdf)). The notification reference "No. 1(13)-Reg.6/83" comes from a secondary blog and is unverified ([employeesforum.online](https://employeesforum.online/family-pension-rules-updated-sep-2024/)). The primary circular PDF failed to fetch, so the before-text and the notification number are not verified against the source.

```json
{
  "ruleset": "survivor-pension",
  "version": "v2",
  "effective_from": "2024-09-10",
  "changes_from": "v1",
  "new_rule": {
    "id": "R7_non_spouse_10yr_cap",
    "applies_when": {"spouse_dead_or_ineligible": true, "claimant_relation_not": "widow", "became_eligible_on_gte": "2024-09-10"},
    "limit": {"default_years": 10, "child": "max(10 years, until age 21)", "disabled_child": "life"},
    "grandfather": "claimants already drawing before 2024-09-10 are unaffected",
    "on_expired": "not_eligible",
    "reason": "NON_SPOUSE_10YR_CAP"
  }
}
```

A good backup change is the divorced-daughter rule. A 2022 Sindh circular excluded daughters divorced after the father's death. On 30-07-2025 the Supreme Court held that **divorce timing is irrelevant**, struck down the circular, and cited Articles 9, 14, 25 and 27 ([The Nation](https://www.nation.com.pk/30-Jul-2025/divorced-daughters-entitled-to-father-s-pension-rules-sc); [Dunya News](https://dunyanews.tv/en/Pakistan/897634-divorced-daughters-entitled-to-fathers-pension-rules-sc)).

### 1.4 Where the notes conflict with team-repo/docs

`01-IDEA.md` step 11, `03-ARCHITECTURE.md` rule 4 ("must not have remarried (v1). v2 changes this") and the `05-DEMO-SCRIPT.md` button "Publish rule v2: Remarried widows stay eligible" all use a change for which **no primary source was found between 2023 and 2026**. The notes found no Federal Shariat Court ruling and no rule change on widow remarriage. The only "till re-marriage" text found applies to widowed and divorced daughters ([SHC](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)). A Facebook post about a 02-12-2024 rule 4.10 amendment limiting spouses to 10 years is unverified and should not be used ([Facebook group](https://www.facebook.com/groups/1820724834863305/posts/4153444204924678/)). A related gap: the idea doc's "an officer will check within 3 days" has no source. No official processing time was found, and one refusal took about 10 months to reverse in court ([SHC](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)). Keep "3 days" only as a mock service level.

### What we should build/do

Encode R1 to R6 as ruleset v1, and add R7 (the 10-year cap with grandfathering) as v2. Rewrite the three doc passages and the judge-console button to "Publish rule v2: 10-year cap for non-spouse heirs (2024-09-10)". Seed the Digital Twin with about 5 past cases where the widow died more than 10 years ago and a child or daughter now claims. Only those with `became_eligible_on >= 2024-09-10` should change. Drop "not remarried" as a v1 widow condition, or keep it only as a labelled mock field. Keep the shares rule visible in the officer view so that a second widow who appears in the FRC is shown as a lawful co-sharer.

## 2. Real pension fraud is mostly fake records, and claimant scams come second

Pakistan's documented losses come mostly from ghost pensioners, payments after death and record tampering, not from outsiders. **The Karachi Development Authority paid Rs667 million to 500 bogus pensioners even though the bank ran biometric checks every six months** ([Dawn](https://www.dawn.com/news/1904287/kda-paid-rs667m-to-500-bogus-pensioners-sindh-pac-finds)). **EOBI paid Rs2.79bn to 5,131 people whose ages had been altered.** It used matriculation-certificate DOBs that conflicted with CNIC data, and now pays on NADRA CNIC data ([The News](https://www.thenews.com.pk/print/1304620-pac-told-eobi-paid-rs2-79bn-to-over-5-000-fake-pensioners)). In Sindh, "a fictitious woman was portrayed as the widow" and paid Rs4.3 million (snippet only) ([The Nation](https://www.nation.com.pk/01-Sep-2024/massive-pension-fund-fraud-uncovered-in-sindh-district-accounts-offices)). That is the real form of the prototype's fake-heir scenario. AGP auditors in South Punjab required life certificates and **no-remarriage certificates** in family pension cases (snippet only) ([Express Tribune](https://tribune.com.pk/story/2583170/audit-flags-financial-irregularities-worth-billions-in-southern-punjab)). A BISP audit found 12,078 government employees, pensioners and spouses paid Rs515.7m despite being excluded (snippet only) ([Express Tribune](https://tribune.com.pk/story/2639218/bisp-audit-reveals-rs257-billion-irregularities)). Forged death certificates appear in property and insurance cases (snippets only) ([Daily Times](https://dailytimes.com.pk/78710/property-worth-billions-transferred-on-fake-death-certificates/); [ARY News](https://arynews.tv/fia-mother-faking-death-fake-insurance-children)). The notes found no Pakistani source on competing widows, payout-account takeover, or impersonation of AGPR.

### 2.1 Official channels: one sender rule, and it can be spoofed

BISP is the only body with a clear statement. **Genuine messages come "from 8171 only", the helpline is 0800-26477, and any fee demand is fraud** (snippet only) ([Geo](https://www.geo.tv/latest/545927-bisp-cautions-beneficiaries-against-fake-messages); [APP](https://www.app.com.pk/national/bisp-cautions-citizens-about-fraudulent-messages-2/)). Yet in 2024 BISP and PTA dealt with calls and messages masked as "8171" (snippet only) ([Radio Pakistan](https://radio.gov.pk/11-01-2024/people-warns-of-fraud-in-bisp-name)). PSCA says e-challans come only from 9915 with no payment links ([ProPakistani](https://propakistani.pk/2026/04/16/psca-warns-citizens-about-e-challan-sms-scam/)). PTA says no genuine courier asks for a verification code ([Profit](https://profit.pakistantoday.com.pk/2025/07/24/pta-warns-public-against-fake-courier-messages-seeking-verification-codes)). EOBI helplines are dated and conflicting: 08000-3624 and 0800-3624 ([Business Recorder](https://www.brecorder.com/news/40076165); [Express Tribune](https://tribune.com.pk/story/1162602/entertainment)). The PTA forwarding code ("420" vs "9915") is unverified ([scamcheck.tech](https://scamcheck.tech/scams/bisp-scam-pakistan)). No AGPR SMS sender was found. PECA offences are now handled by the NCCIA (Wikipedia, secondary) ([Wikipedia](https://en.wikipedia.org/wiki/National_Cyber_Crimes_Investigation_Agency)).

### 2.2 Global controls give concrete numbers to copy

The UK and US rely on death feeds and account checks. **UK State Pension fraud was 0.0% (£0m), with 0.1% (£190m) overpaid**, mostly through official and claimant error, against 3.3% across all benefits in FYE 2025 ([GOV.UK](https://www.gov.uk/government/statistics/fraud-and-error-in-the-benefit-system-financial-year-2024-to-2025-estimates/fraud-and-error-in-the-benefit-system-financial-year-ending-fye-2025)). Tell Us Once passes a registered death to DWP and some public pension schemes ([GOV.UK](https://www.gov.uk/after-a-death/organisations-you-need-to-contact-and-tell-us-once)). In the US, Treasury access to the full SSA death file prevented or recovered **more than $31m in a five-month pilot** (snippet only) ([Treasury](https://home.treasury.gov/news/press-releases/jy2784)). In an older review, 68% of payees overpaid after a beneficiary's death were relatives (snippet only) ([SSA OIG](https://oig-files.ssa.gov/audits/full/html/96-61202.html)).

The thresholds conflict in places. SSA's 18 March 2025 press release moves direct-deposit changes to **one business day**, ending a 30-day online hold (snippet only) ([SSA](https://www.ssa.gov/news/en/press/releases/2025-03-18.html)). But SSA's blog says online changes are "still subject to the 30-day hold", and the conflict is unresolved ([SSA blog](https://www.ssa.gov/blog/en/posts/2025-03-18.html)). SSA also checks the bank account through Treasury's Account Verification Service ([SSA blog](https://www.ssa.gov/blog/en/posts/2025-03-18.html)). UK firms may delay a suspicious outbound payment **for at most 4 business days**, and the guidance says this should not be applied automatically in every case (snippet only) ([FCA FG24/6](https://fca.org.uk/publication/finalised-guidance/fg24-6.pdf)). Confirmation of Payee returns match, close match or no match. It does not block payments, and money sent after a no-match may not be recoverable ([UK Finance](https://www.ukfinance.org.uk/news-and-insight/blogs/changing-name-game-confirmation-payee); [Virgin Money](https://uk.virginmoney.com/service/cop/)). The PSR reports more than 2.5bn checks covering more than 99% of Faster Payments (snippet only) ([PSR](https://www.psr.org.uk/news-and-updates/latest-news/news/fraud-prevention-is-key-during-international-fraud-awareness-week/)). Pay.UK reports a 59% drop in one misdirected-payment category, but that figure is vendor-reported and was not independently checked ([Pay.UK](https://www.wearepay.uk/pay-uk-discusses-the-evolution-of-confirmation-of-payee-with-tell-money/)). No Pakistani cooling-off period for changing a payout account was found.

### What we should build/do

Keep SafeSwitch's 48h hold with PIN or voice confirmation, and describe it as sitting between SSA's one business day and the UK's 4-day maximum. Extend the hold to 4 business days when a red flag fires: account used by another claim, a payee close match or no match, or a change soon after the death is reported. Add a mock CoP call before every payout, mapping match to AUTO, close match to ASK_PROOF and no match to UNSURE. Use NADRA CNIC DOB as the single source of truth, following the EOBI fix. Add an "already drawing or excluded" cross-check, and a family-record check that separates a lawful second widow from a fictitious one. In Scam Shield, weight fee, code, link and unverified-payment rules above the sender ID. Show real short codes in the README as real-world patterns only, and use mock senders in the app. Put the KDA case on a slide: periodic biometrics alone did not stop Rs667m in losses.

## 3. Name matching must lean on CNIC, because "Muhammad" carries almost no evidence

Pakistani names vary by transliteration (Mohammad vs Muhammad). They can appear "in any order", may carry a caste prefix, and do not always include a family name. A woman may use her father's name and later her husband's ([GOV.UK Pakistan profile](https://www.gov.uk/government/publications/pakistan-knowledge-base-profile/pakistan-knowledge-base-profile)). The CNIC has a mandatory father's-name field, and since 2021 NADRA lets married women keep their father's name there ([Wikipedia: CNIC](https://www.wikipedia.org/wiki/CNIC_(Pakistan)); [Dawn](https://www.dawn.com/news/1652563)). So **Zainab's CNIC may not name Aslam at all**, and a mismatch in that field must count as weak evidence. The passport authority still requires the husband's name ([Arab News PK](https://www.arabnews.pk/node/2516036)).

In one informal Arabic-name test, a Levenshtein ratio threshold of 75 gave 88% accuracy on 50 names. It missed "Mohamad"/"Muhammed" (score 67) and falsely matched "Wesam"/"Esam" (89). **Soundex and Double Metaphone mapped seven distinct names (Hasan, Hussam and others) to a single code** ([WS-DL blog](https://ws-dl.blogspot.com/2020/12/2020-12-28-tools-and-libraries-for.html)). rapidfuzz's `token_sort_ratio` ignores word order. `token_set_ratio` returns 100 when one name is a subset of the other ([RapidFuzz](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html)), which is too permissive for payouts ("Aslam" vs "Muhammad Aslam"). Splink's Fellegi-Sunter guide sums log2(m/u) per field and uses term-frequency adjustment so that common values such as "Muhammad" weigh less ([Splink](https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html); [Splink TF](https://moj-analytical-services.github.io/splink/topic_guides/comparisons/term-frequency.html)). OFAC sets no threshold and leaves the choice to the screener ([OFAC](https://ofac.treasury.gov/faqs/topic/1636)). Unlike sanctions screening, this pipeline has ID numbers and birth dates, which carry most of the evidence ([OpenSanctions](https://www.opensanctions.org/articles/2025-06-24-name-matching.md)).

| Stage | Design (thresholds are proposals to tune, not cited values) |
|---|---|
| Parse | Split on s/o, w/o, d/o, bin, bint, ibn. Strip honorifics (Syed, Sheikh, Haji, Chaudhry, Malik, Begum, Bibi, Mst) into a low-weight field. This Pakistani list beyond GOV.UK's titles is unverified and comes from domain knowledge. |
| Canonicalise | Mohd, Md, M., Mohammad, Mohammed and Muhammed all map to `muhammad`. Expand "M." only when the other record has a Muhammad-family token. |
| Block | CNIC exact, OR key token plus birth year, OR phonetic key plus district. Phonetic codes are used only to propose pairs. |
| Score | Name `token_sort_ratio` with Muhammad down-weighted, in bands >=95 / 85-95 / 70-85 / <70. CNIC exact / one-digit typo / different / missing. DOB exact / year / ±1 / different / missing. |
| Route | p >= 0.95, CNIC exact and no flag: auto-match. 0.70-0.95: ask for the missing field. Below 0.70, a CNIC conflict, or two candidates above 0.70: UNSURE. **No auto-match without an exact CNIC.** Never auto-reject. |

For synthetic evaluation, generate seeded identities and corrupt them with transliteration swaps, abbreviations, reordering, dropped family names, added or removed honorifics, s/o vs w/o swaps, CNIC and DOB OCR digit errors, and missing DOB. Add hard negatives: a second person with the same full name, same name and birth year, siblings, and a CNIC one digit off. Report the false-match rate, false non-match rate, UNSURE rate and blocking recall, and plot them against the threshold. The WS-DL design of many names times many variants, compared pairwise, is a usable template ([WS-DL](https://ws-dl.blogspot.com/2020/12/2020-12-28-tools-and-libraries-for.html)). Results will not reflect real NADRA error rates, so state that as a limit.

### What we should build/do

Build the five-stage pipeline exactly as in the table, with field levels and weights saved into the auditor trace. Generate about 500 identities with variants and hard negatives, including the seeded second Muhammad Aslam. Set the auto-match threshold where the false-match rate on hard negatives is 0, then check that 0.95 still holds. Show both curves on the evaluation page. Do not use `token_set_ratio` or phonetic codes as match evidence.

## 4. Forgery checks are weak signals and must be shown that way

No single cheap method is reliable on phone photos of documents. ELA highlights regions with a different JPEG history, but a change can spread across an 8x8 block, and a repeatedly resaved image goes almost black ([FotoForensics](https://fotoforensics.com/tutorial-ela.php)). Its originator said "It is up to the user to interpret the results" ([Wikipedia](https://en.wikipedia.org/wiki/Error_level_analysis)). ELA weakens under compression and scaling ([IIETA](https://iieta.org/download/file/fid/192306)). **In document benchmarks, median tampered area is only 0.27% to 0.97% of pixels in several datasets**, and sensor-noise cues fail on scanned documents ([DocForge-Bench](https://arxiv.org/html/2603.01433v1)). WhatsApp chat transfers removed all EXIF in one 2025 study, while document-mode transfers kept it ([SciEPublish](https://www.sciepublish.com/article/pii/567)). So **missing EXIF is normal and must not count against the applicant**.

Tesseract ships an official Urdu model ([Tesseract data files](https://tesseract-ocr.github.io/tessdoc/Data-Files.html)), but no accuracy figure for Nastaliq or for photographed certificates was found. The CNIC has 13 digits ([Wikipedia](https://en.wikipedia.org/wiki/CNIC_(Pakistan))). An OECD document's grouping conflicts with the 5-7-1 grouping ([OECD](https://www.oecd.org/content/dam/oecd/en/topics/policy-issue-focus/aeoi/pakistan-tin.pdf)), and the gender-digit rule is unverified. Keypoint copy-move detection with SIFT or ORB beats block methods on natural images ([Semantic Scholar](https://www.semanticscholar.org/paper/7f0e9d3ed7eaa3a951534033200d168652f26986)), but repeated text glyphs cause false matches. That limits it to seals and stamps. SIFT in main OpenCV since 4.4.0 is unverified against the release notes ([guide](https://opencv-windows.github.io/opencv-contrib-windows.html)). No public dataset of forged Pakistani certificates exists. DocTamper's 170,000 images are synthetic ([CVPR 2023](https://openaccess.thecvf.com/content/CVPR2023/papers/Qu_Towards_Robust_Tampered_Text_Detection_in_Document_Image_New_Dataset_CVPR_2023_paper.pdf)).

**QR verification is not confirmed.** NADRA's page says the provincial CRMS issues birth, death, marriage and divorce certificates across 11,000+ Union Councils, but it does not mention QR codes ([NADRA ecosystem](https://www.nadra.gov.pk/ecosystem)). The QR claim appears only on a law-firm marketing page and an unofficial aggregator ([Right Law](https://rightlaw.com.pk/nadra-certificates-in-pakistan-marriage-divorce-birth-death-certificates/); [trackingidcheckonline.pk](https://trackingidcheckonline.pk/nadra-death-certificate-online-check/)). Automation-bias research says reviewers defer to scores, and that supportive information works better than commands ([Goddard et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC3240751/); [CSET](https://cset.georgetown.edu/publication/ai-safety-and-automation-bias/)).

### What we should build/do

Rank checks by evidence: (1) OCR format and registry cross-check by CNIC and DOB; (2) copy-move limited to seal regions, with a match count tuned on mock images; (3) ELA on the original upload, shown next to the image; (4) EXIF recorded as context only; (5) optional QR decode, where "no QR found" is a neutral state. Show a list of indicators, each with evidence and a "what this cannot tell" line, using labels like "needs a second look", and never "fake". Do not roll them into a single forgery score. Log officer disagreement for the evaluation page. Build a labelled mock set with each image in original, WhatsApp-recompressed and screenshot form. The team docs never claim QR verification. Keep it that way, and add a line to `02-COMPLIANCE.md` "honest limits" that QR verification is not built.

## 5. Low-literacy design means voice on every screen and a 170 KB shell

Microsoft Research India's text-free interfaces were tested with low-literate women in urban slums ([Medhi et al., ICTD 2006](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/medhi_ictd2006.pdf)), and later MSR work found textual interfaces unusable for low-literate users ([COMPASS 2022](https://www.microsoft.com/en-us/research/wp-content/uploads/2022/05/compass22-34-taps.pdf)). The claims that semi-abstract cartoons beat abstract icons and that numerals are readable are unverified. Pakistan's voice services prove reach: **Polly drew 165,000 users and 636,000 interactions in about a year** ([Raza et al.](https://aghaaliraza.com/papers/2013-behavior-analysis-of-low-literate-users-of.html)). Shared, intermediated phone use is normal for South Asian women ([Sambasivan et al., SOUPS 2018](https://www.usenix.org/system/files/conference/soups2018/soups2018-sambasivan.pdf)), which makes Helper Mode the default case. **Pakistan has 81% mobile broadband coverage but only 29% mobile internet use** ([GSMA](https://www.gsma.com/newsroom/press-release/unlocking-pakistans-digital-future-gsma-highlights-opportunities-and-progress-at-digital-nation-summit-islamabad/)).

Azure has ur-PK neural voices, UzmaNeural and AsadNeural ([Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/5921704/urdu-as-support-voice-typing)). Pricing is **$15 per 1M characters, with 0.5M free per month** ([Azure pricing](https://azure.microsoft.com/en-us/pricing/details/speech/)). Google lists only ur-IN voices ([Google](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types)). Whether Azure supports ur-PK speech-to-text is unverified. Whisper-small Urdu WER runs from about 27 to 56 across test sets ([arXiv 2409.11252](https://arxiv.org/html/2409.11252v3)), so every value filled by voice needs a tap to confirm. web.dev's slow-3G budget is **about 170 KB total (JS 100 KB) with TTI under 5 s** ([web.dev](https://web.dev/articles/your-first-performance-budget)). Background Sync works only in Chromium browsers, and not in Android WebView, Firefox or Safari ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Background_Synchronization_API)). The Idempotency-Key header is an IETF draft, not an RFC; it uses 409 for concurrent use ([IETF](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header)). `navigator.storage.persist()` protects IndexedDB from eviction ([web.dev](https://web.dev/articles/persistent-storage)). Dexie details were not checked against current docs.

### What we should build/do

Budget the citizen shell at 170 KB or less (JS 100 KB or less), each later screen at 30 KB or less, each audio clip at about 15 KB or less, and photos compressed on the device to about 200 KB. These are our own numbers, derived from web.dev. Pre-generate about 60 prompts with UzmaNeural (about 6,000 characters, well inside the free tier), and build dynamic reasons from cached clips per reason code. Create the outbox key as a UUID when the user taps save. Flush on `sync`, app open, the `online` event, and a "Send now" button. The server keeps a unique key per principal, replays the stored response, returns 422 for a reused key with a different body and 409 while a request is in flight. Partition the outbox by family in Helper Mode. Send payout confirmations to the widow directly, never to the helper's phone. A mock "call to hear status" IVR line is a cheap extra.

## 6. Jev reads small facts from text and images, and code decides

Images and Box on jev-1.14.0 are "dreamer-ready", not production. They require the `TypeSafe-Danger-Zone-Images: true` header, or the request returns 400 ([Images](https://docs.typesafe.ai/images.md); [Box](https://docs.typesafe.ai/primitives/box.md)). The limits are strict: **PNG or JPEG only, 16 MiB per file, each side 280-1568 px, 78,400-2,458,624 total pixels, 32 MiB per request. Out-of-range images are "rejected, never resized", and the whole request fails.** The API strips EXIF without applying its orientation, so rotate the pixels before sending. Use a fresh UUID reference for each image, and put a shared image in `state` once ([Images](https://docs.typesafe.ai/images.md)). Box returns fractional coordinates plus a confidence, has no recommended threshold (the example uses 0.6), and **"A Box answer is always a box"**. It must therefore be paired with a presence Noul ([Box](https://docs.typesafe.ai/primitives/box.md)).

In the scanned-record cookbook, present items scored ≥0.97 and look-alikes ≤0.02. A covered date came back `unreadable` with legible = 0.05. Combining reading and judging in one question let bad dates pass, so the cookbook splits them ([Reading scanned documents](https://docs.typesafe.ai/cookbooks/reading_scanned_documents.md)). In the OCR cookbook, a page check plus a crop check, flagging when either is below 0.25, caught all 3 misreads among 15 fields; neither check alone caught all three ([OCR confidence](https://docs.typesafe.ai/cookbooks/ocr_confidence_bounding_boxes.md)). These samples are anecdotal. A Choice "always picks an option": a lamp complaint scored 0.96 on a product while its companion Noul read 0.02. So **read a Choice only when the companion Noul is above 0.7 and the top choice is above 0.7, and send everything else to a person** ([Companion Noul](https://docs.typesafe.ai/patterns/companion-noul.md)). Images cost the normal input price, with no estimator. Image latency is unpublished, and the cookbooks use a 120 s timeout ([Images](https://docs.typesafe.ai/images.md)). No docs claim tamper detection or Urdu reading.

| Set | Questions (our draft, untested) |
|---|---|
| A. Intake (text) | `claim_type` Choice (new claim / status / payout change / correction / scam check, order shuffled) + `claim_type_fits` Noul; `claimant_relation` Choice + `relation_fits`; `mentions_other_claimant` Noul; `account_change_requested` Noul |
| B. Document (image) | `doc_kind` Choice + fits Noul; `is_death_certificate`; `stamp_visible` + `stamp_box`; `signature_visible` + box; `deceased_name_legible`; `death_date_legible`; `name_matches_ocr` on the page and again on a crop; `death_year` Choice with `other`/`unreadable`; `image_quality` Score; `looks_altered` labelled UNVERIFIED |
| C. Scam SMS (text) | `asks_fee`, `asks_secret`, `has_link` (plus a regex), `claims_government`, `urgency`, `claims_payment_ready` (cross-checked against the case in code), `addresses_reader_instructions` (injection sensor) |

### What we should build/do

Pin `jev-1.14.0`. Use a real OCR step to extract fields, then Jev to verify them on the page and on a crop. Keep date arithmetic, registry matching and the scam verdict in code. Put untrusted text under labelled state keys such as `untrusted_message`. Normalise each image (rotate, fit to 1568 px, convert to baseline JPEG) before sending. Log the model, usage, every probability, the question-set version, an image SHA-256 (not the image), thresholds and route. Measure image latency p50 and p95 early, and route to UNSURE on timeout. The 0.95 gate applies to the combined decision, not to any single Jev answer. This matches `03-ARCHITECTURE.md`.

## 7. Team-size rule risk

The team is 2 people. Per the team's decision, this changes nothing: scope, streams and plans stay at the full 3-4 person level described in `04-BUILD-PLAN.md`, with no change to team size.

### What we should build/do

Build the full planned scope as written.

## Conclusion

The research moves the prototype from plausible to grounded in one respect that judges can check: every rule, hold and threshold now traces either to a dated Pakistani rule or court order or to a published foreign control. The remarried-widow example was the one piece of story that could fail a fact check, and the 10-year cap replaces it with a better demo. The cap carries its own grandfather clause, which gives the Digital Twin a real reason to show "decided under v1". The deeper finding is that Pakistan's largest losses came from fake records that passed periodic checks, not from clever outsiders. That makes registry cross-matching on CNIC and DOB more central to the pitch than any image forensics. Forensics, the Jev document questions and the scam sensors are honest only when presented as indicators with published limits.

## Sources

| URL | What it supports |
|---|---|
| https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz | Rule 4.10 text, widow first, share split, order of succession, daughters till remarriage, 10-month delay |
| https://scp.gov.pk/judgments/c.p._616_k_2025.pdf | Rule 4.10(3) on unmarried females' marriage (snippet only) |
| https://www.scribd.com/document/1024090169/Family-Pension-Eligibility-for-Father | Parents as recipients (unverified) |
| https://www.facebook.com/StartupPakistanSP/posts/the-supreme-court-of-pakistan-has-ruled-that-the-widow-not-the-siblings-is-the-l/1460257622804876/ | Widow over siblings (unverified) |
| https://www.brecorder.com/news/40310086 | 10-year cap wording; single pension rule |
| https://mettisglobal.news/govt-fixes-family-pension-at-10-years-after-death/ | 10-year cap, 2024-09-10, child to 21, Special Family Pension |
| https://www.thenews.com.pk/print/1241684-existing-family-pensioners-exempted-from-10-year-limit | Existing pensioners exempt |
| https://www.finance.gov.pk/circulars/circular_03012025.pdf | 03-01-2025 circular (snippet only) |
| https://employeesforum.online/family-pension-rules-updated-sep-2024/ | Notification number (unverified) |
| https://www.facebook.com/groups/1820724834863305/posts/4153444204924678/ | Spouse 10-year amendment claim (unverified) |
| https://finance.punjab.gov.pk/details/pension-reforms | Punjab spouse-only revision (snippet) |
| https://www.nation.com.pk/30-Jul-2025/divorced-daughters-entitled-to-father-s-pension-rules-sc | SC divorced-daughter ruling; delay is punishable |
| https://dunyanews.tv/en/Pakistan/897634-divorced-daughters-entitled-to-fathers-pension-rules-sc | Same ruling |
| https://legalpk.com/blog-post/eobi-pension-claim-process-pakistan | Documents, EOBI process, DOB mismatch, NADRA stalls |
| https://www.passco.gov.pk/wp-content/uploads/2023/11/Widow-Pension-Form.pdf | Widow form requirements |
| http://www.eobi.gov.pk/announcement/Pension-Account/Survivor-form.pdf | EOBI survivor form documents |
| http://www.eobi.gov.pk/introduction/Pension.html | EOBI minimum Rs 10,000 (snippet) |
| https://gopunjab.pk/eobi-pension/ | Rs 11,500 minimum (secondary) |
| https://www.linkedin.com/pulse/eobi-gratuity-provident-fund-what-every-pakistani-worker-zahid-rulef | Rs 11,500 minimum (secondary) |
| https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Nsa-sg-jjjjjjjjjjjjj.html | EOBI Act (not fetched) |
| https://www.dawn.com/news/1904287/kda-paid-rs667m-to-500-bogus-pensioners-sindh-pac-finds | KDA Rs667m, 6-month biometrics |
| https://www.thenews.com.pk/print/1304620-pac-told-eobi-paid-rs2-79bn-to-over-5-000-fake-pensioners | EOBI Rs2.79bn, age tampering, NADRA DOB fix |
| https://www.nation.com.pk/01-Sep-2024/massive-pension-fund-fraud-uncovered-in-sindh-district-accounts-offices | Fictitious widow (snippet) |
| https://tribune.com.pk/story/2583170/audit-flags-financial-irregularities-worth-billions-in-southern-punjab | Life and no-remarriage certificates (snippet) |
| https://tribune.com.pk/story/2639218/bisp-audit-reveals-rs257-billion-irregularities | BISP excluded pensioners paid (snippet) |
| https://dailytimes.com.pk/78710/property-worth-billions-transferred-on-fake-death-certificates/ | Forged death certificate, property (snippet) |
| https://arynews.tv/fia-mother-faking-death-fake-insurance-children | Fake death certificate, insurance (snippet) |
| https://www.geo.tv/latest/545927-bisp-cautions-beneficiaries-against-fake-messages | BISP 8171, helpline (snippet) |
| https://www.app.com.pk/national/bisp-cautions-citizens-about-fraudulent-messages-2/ | BISP no-fee rule (snippet) |
| https://radio.gov.pk/11-01-2024/people-warns-of-fraud-in-bisp-name | 8171 masking (snippet) |
| https://propakistani.pk/2026/04/16/psca-warns-citizens-about-e-challan-sms-scam/ | PSCA 9915, no links |
| https://profit.pakistantoday.com.pk/2025/07/24/pta-warns-public-against-fake-courier-messages-seeking-verification-codes | No verification codes |
| https://www.brecorder.com/news/40076165 | EOBI helpline, biometrics (dated) |
| https://tribune.com.pk/story/1162602/entertainment | EOBI helpline (dated) |
| https://scamcheck.tech/scams/bisp-scam-pakistan | PTA forwarding code (unverified) |
| https://en.wikipedia.org/wiki/National_Cyber_Crimes_Investigation_Agency | NCCIA handles PECA (secondary) |
| https://www.gov.uk/government/statistics/fraud-and-error-in-the-benefit-system-financial-year-2024-to-2025-estimates/fraud-and-error-in-the-benefit-system-financial-year-ending-fye-2025 | DWP rates, State Pension 0.0% fraud |
| https://www.gov.uk/after-a-death/organisations-you-need-to-contact-and-tell-us-once | Tell Us Once |
| https://home.treasury.gov/news/press-releases/jy2784 | Death file pilot $31m (snippet) |
| https://oig-files.ssa.gov/audits/full/html/96-61202.html | 68% overpaid payees were relatives (snippet) |
| https://www.ssa.gov/news/en/press/releases/2025-03-18.html | One-business-day direct-deposit change (snippet) |
| https://www.ssa.gov/blog/en/posts/2025-03-18.html | 30-day hold conflict, Account Verification Service (snippet) |
| https://fca.org.uk/publication/finalised-guidance/fg24-6.pdf | 4-business-day payment delay (snippet) |
| https://www.ukfinance.org.uk/news-and-insight/blogs/changing-name-game-confirmation-payee | CoP outcomes |
| https://uk.virginmoney.com/service/cop/ | CoP does not block payments |
| https://www.psr.org.uk/news-and-updates/latest-news/news/fraud-prevention-is-key-during-international-fraud-awareness-week/ | CoP scale (snippet) |
| https://www.wearepay.uk/pay-uk-discusses-the-evolution-of-confirmation-of-payee-with-tell-money/ | CoP effect, vendor-reported (snippet) |
| https://www.gov.uk/government/publications/pakistan-knowledge-base-profile/pakistan-knowledge-base-profile | Pakistani name structure, titles |
| https://www.wikipedia.org/wiki/CNIC_(Pakistan) | Father/husband field |
| https://www.dawn.com/news/1652563 | NADRA 2021 father's-name option |
| https://www.arabnews.pk/node/2516036 | Passport husband's-name conflict |
| https://ws-dl.blogspot.com/2020/12/2020-12-28-tools-and-libraries-for.html | Arabic name test, phonetic over-merging, evaluation template |
| https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html | token_sort and token_set behaviour |
| https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html | Fellegi-Sunter weights |
| https://moj-analytical-services.github.io/splink/topic_guides/comparisons/term-frequency.html | Term-frequency adjustment |
| https://ofac.treasury.gov/faqs/topic/1636 | No fixed OFAC threshold |
| https://www.opensanctions.org/articles/2025-06-24-name-matching.md | IDs and DOB disambiguate |
| https://fotoforensics.com/tutorial-ela.php | ELA method and caveats |
| https://en.wikipedia.org/wiki/Error_level_analysis | Krawetz quote |
| https://iieta.org/download/file/fid/192306 | ELA degrades under post-processing |
| https://arxiv.org/html/2603.01433v1 | Tampered-area fractions, sensor noise limits, benchmarks |
| https://www.sciepublish.com/article/pii/567 | WhatsApp strips EXIF |
| https://tesseract-ocr.github.io/tessdoc/Data-Files.html | Tesseract Urdu model |
| https://en.wikipedia.org/wiki/CNIC_(Pakistan) | 13-digit CNIC |
| https://www.oecd.org/content/dam/oecd/en/topics/policy-issue-focus/aeoi/pakistan-tin.pdf | CNIC structure, grouping conflict |
| https://www.semanticscholar.org/paper/7f0e9d3ed7eaa3a951534033200d168652f26986 | Keypoint copy-move review |
| https://opencv-windows.github.io/opencv-contrib-windows.html | SIFT in main OpenCV (unverified) |
| https://openaccess.thecvf.com/content/CVPR2023/papers/Qu_Towards_Robust_Tampered_Text_Detection_in_Document_Image_New_Dataset_CVPR_2023_paper.pdf | DocTamper dataset |
| https://www.nadra.gov.pk/ecosystem | CRMS certificates, no QR mention |
| https://rightlaw.com.pk/nadra-certificates-in-pakistan-marriage-divorce-birth-death-certificates/ | QR claim (commercial, unverified) |
| https://trackingidcheckonline.pk/nadra-death-certificate-online-check/ | QR claim (unofficial, unverified) |
| https://pmc.ncbi.nlm.nih.gov/articles/PMC3240751/ | Automation bias mitigation |
| https://cset.georgetown.edu/publication/ai-safety-and-automation-bias/ | Human-in-the-loop over-trust |
| https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/medhi_ictd2006.pdf | Text-free UI study |
| https://www.microsoft.com/en-us/research/wp-content/uploads/2022/05/compass22-34-taps.pdf | Text UIs unusable for low-literate users |
| https://aghaaliraza.com/papers/2013-behavior-analysis-of-low-literate-users-of.html | Polly reach in Pakistan |
| https://www.usenix.org/system/files/conference/soups2018/soups2018-sambasivan.pdf | Shared phones, intermediated use |
| https://www.gsma.com/newsroom/press-release/unlocking-pakistans-digital-future-gsma-highlights-opportunities-and-progress-at-digital-nation-summit-islamabad/ | 81% coverage, 29% use |
| https://learn.microsoft.com/en-us/answers/questions/5921704/urdu-as-support-voice-typing | ur-PK Azure voices |
| https://azure.microsoft.com/en-us/pricing/details/speech/ | TTS pricing, free tier |
| https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types | Google only ur-IN |
| https://arxiv.org/html/2409.11252v3 | Urdu Whisper WER |
| https://web.dev/articles/your-first-performance-budget | 170 KB slow-3G budget |
| https://developer.mozilla.org/en-US/docs/Web/API/Background_Synchronization_API | Background Sync support |
| https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header | Idempotency-Key draft |
| https://web.dev/articles/persistent-storage | Persistent storage |
| https://docs.typesafe.ai/images.md | Jev image limits, header, preparation, billing |
| https://docs.typesafe.ai/primitives/box.md | Box output, no threshold, always a box |
| https://docs.typesafe.ai/cookbooks/reading_scanned_documents.md | Field reading, unreadable option, split requests |
| https://docs.typesafe.ai/cookbooks/ocr_confidence_bounding_boxes.md | Page plus crop check, 0.25 flag |
| https://docs.typesafe.ai/patterns/companion-noul.md | Choice plus companion Noul routing |
| https://docs.typesafe.ai/primitives/choice.md | Option descriptions, up to 255 options |
| https://docs.typesafe.ai/cookbooks/llm_guardrails.md | Atomic Noul battery thresholds |
