# Ground the widow's claim in real rules

> PROTOTYPE research for Coder's Cup 2026. All people, records and services in the build are mock. Most claims below carry a URL. Claims with no URL are either marked "unverified" or labelled as our own design choice or inference. Items marked "unverified", "(snippet only)" or "unverified (source unreachable)" are not presented as fact.

> **Verification (2026-11-21).** Every cited claim was re-checked against its source. Five verification passes were run (A to E). P = primary source, S = secondary source.
>
> | Pass and report section | Verified | Partial | Not supported | Unreachable | Other |
> |---|---|---|---|---|---|
> | A: summary and section 1 | 28 | 7 | 3 | 3 | 2 unverified (no source exists, accepted) |
> | B: section 2 | 19 | 8 | 1 | 1 | 0 |
> | C: sections 3 and 4 | 28 | 7 | 1 | 1 | 0 |
> | D: sections 5, 6, 7 and conclusion | 21 | 6 | 0 | 0 | 2 not checked (negative claim; no citation) |
> | E: rule v1 to v2, remarriage, 10-year cap | not tallied | | | | Remarriage claim: verified for widows under civil-service family pension, partial overall (PHC widower case, EOBI). 10-year cap: verified in substance from the primary OM, with corrections. |
>
> Partial and not-supported rows now use the corrected wording from the verify files. Unreachable sources were removed, or the claim is marked "unverified (source unreachable)". Pass E is authoritative for section 1.3.

## Summary of decisions for the build team (1 page)

The research supports the team's design, with one forced correction. **The planned rule v2 ("remarried widows keep the pension") is not supported. No federal or provincial civil-service rule or court ruling found, as of 2026-11-21, lets a remarried widow keep government family pension.** Swap it for the federal 10-year cap on Ordinary Family Pension for heirs after the spouse. The cap comes from Finance Division O.M. F.No. 9(3)R-6/2024-264 dated 10-09-2024, which took effect "with immediate effect" ([Finance Division OM, P](https://www.finance.gov.pk/circulars/circular_10092024_1.pdf)). Two later Finance Division OMs settle the grandfathering: 10-10-2024 and 22-01-2025 ([OM 10-10-2024, P](https://www.finance.gov.pk/circulars/circular_10102024_1.pdf); [OM 22-01-2025, P](https://www.finance.gov.pk/circulars/circular_22012025.pdf)). The change is dated, has exact primary wording and has a grandfather clause, so the Digital Twin can show a real "this would change N past decisions" result. Our design inference is that it leaves Zainab's own claim as a widow untouched, because the cap applies only "after the death or ineligibility of the spouse". The other decisions follow.

| # | Decision | Basis |
|---|---|---|
| 1 | Versioned ZEN rules. v1 = federal O.M. No. 1(13)-Reg.6/83 (23-10-1983) as updated 24-06-2024. v2 = O.M. F.No. 9(3)R-6/2024-264 (10-09-2024) plus clarifications of 10-10-2024 and 22-01-2025. A widow's pension stops on remarriage in both versions. Family pensions that started before 10-09-2024 keep v1. | Sections 1.2 and 1.3 |
| 2 | Change three team docs: `01-IDEA.md` step 11, `03-ARCHITECTURE.md` rule 4, `05-DEMO-SCRIPT.md` "Publish rule v2" button. | Section 1.4 |
| 3 | A second wife who appears in the family record is a lawful co-sharer, not a fake heir. "Rukhsana" must stay "not in the family record" to count as a red flag. | Sindh rule 4.10 split ([SHC, P](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)) |
| 4 | Keep the 48h payout-change hold. Allow up to 4 business days when a red flag fires, and release it as soon as the flag clears. Add a Confirmation-of-Payee-style match / close match / no match check before any payout. | SSA, FCA, UK Finance, Virgin Money (section 2) |
| 5 | Scam Shield: content rules (fee, code, link, unverified money promise) outweigh the sender ID. Official short codes such as 8171 are evidence, never proof. | BISP, PID, PTA, PSCA (section 2) |
| 6 | Name matching: normalise, block, score with Fellegi-Sunter weights. **No auto-match without exact CNIC.** Choose the threshold on a synthetic set where the false-match rate on hard negatives is 0. | Section 3 |
| 7 | Document checks are a list of risk indicators: OCR cross-check, copy-move on seals, ELA, EXIF context, optional QR decode. **Never show "QR verified"**: no primary source confirms that death certificates carry a QR. | Section 4 |
| 8 | Citizen shell at most 170 KB, with pre-generated ur-PK Azure audio. The outbox flushes on app open and on the `online` event, not only through Background Sync. Server idempotency key per IETF draft. | Section 5 |
| 9 | Jev answers small questions only. Use Choice plus a companion Noul for routing, closed-set Choices with `unreadable` for fields, and Box always paired with a presence Noul. Jev is not a tamper detector. | Section 6 |
| 10 | Scope stays at the full 3-4 person plan. | Section 7 |

---

## 1. Pakistan family pension rules fit a small set of JSON rules and one dated change

Provincial pension rules are quoted in full in a Sindh High Court order dated 27.08.2025 (C.P. No. D-198 of 2025, Sukkur bench), and they give a clear order of entitlement ([SHC, P](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)). The widow of a male servant comes first, or the husband of a female servant. With several widows, **if widows plus eligible children "does not exceed 4", the pension is divided equally; otherwise "each surviving widow shall get 1/4th of the pension and the balance(if any) shall be divided equally among the surviving eligible children"** ([SHC, P](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)). The quoted text is internally inconsistent. It says "does not exceed 4" in one place and "more than 3" in another, so n = 4 falls in both branches. The mock rule should pick one reading and state it. If there is no widow, the pension passes to sons "not above 25 years" and unmarried daughters, then down a fixed list that includes "the eldest widowed daughter". A Sindh Finance Department OM, No. FD(SR-III)3-115/2015 dated 07-04-2016 and "applicable w.e.f 01.07.2015", gives widowed and divorced daughters the pension "for life or till her re-marriage" ([SHC, P](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)).

The federal rule is Finance Division O.M. No. 1(13)-Reg.6/83 dated 23-10-1983, read here in the consolidated copy "Updated as on 24.06.2024" ([Finance Division, P](https://www.finance.gov.pk/circulars/circular_24062024.pdf); [original 1983 OM, P](https://www.finance.gov.pk/circulars/circular_23101983.pdf)). The widow draws "for her life, if deceased is a male Government servant" (para 8(2)(a)(i)). Failing a widow, the pension is divided among "son(s) not above 21 years and unmarried daughters(s) / widow daughter(s) / divorced daughter(s) till marriage/remarriage" (para 8(2)(a)(ii), substituted by O.M. No. F.13(16)-Reg.6/2017-516 dated 19.06.2018). So the son age limit is 25 in the quoted Sindh text and 21 in the federal text. The federal wording for several widows was not checked (unverified).

**A widow's government family pension stops on remarriage.** The federal OM says no pension is payable "to a widow female member of a Government servant's family in the event of her re-marriage" (para 8(3)(c)). The next legal beneficiary draws from the date of her remarriage (para 8(5)) ([Finance Division, P](https://www.finance.gov.pk/circulars/circular_24062024.pdf)). Punjab, KP and Sindh have the same rule (section 1.3). Balochistan was not checked (unverified).

The document list comes from EOBI survivor claims, not government family pension. LegalPK, a secondary blog, lists the death certificate, proof of relationship (nikah nama for a widow, FRC for children), the claimant's own CNIC, and a bank account in the claimant's own name ([LegalPK, S](https://legalpk.com/blog-post/eobi-pension-claim-process-pakistan)). The EOBI survivor form asks for an indemnity bond and a nikah nama attested by a Grade-17 officer. If there is no nikah nama, it asks for an affidavit stating the nikah date. The live EOBI host is dead, so the form was read from a Wayback Machine capture of 2023-12-03 ([EOBI survivor form, P](http://www.eobi.gov.pk/announcement/Pension-Account/Survivor-form.pdf)). The phrase "Death certificate issued by Municipality" comes from the PASSCO widow pension form ([PASSCO widow form, P](https://www.passco.gov.pk/wp-content/uploads/2023/11/Widow-Pension-Form.pdf)). A June 2024 **draft** notification said a person entitled to more than one pension of any kind may opt to draw only one, while a spouse's own pay or pension does not bar the family pension ([Business Recorder, S, draft](https://www.brecorder.com/news/40310086)). That is draft text, not a confirmed rule. No source gives the ordinary family pension rate (for example 75% or 100% of the deceased's pension), so that is unverified. The mock should use a made-up amount and label it.

### 1.1 EOBI is a second, simpler scheme

The EOBI pension page lists "Pension Rates: Minimum RS. 10,000/= ... Maximum As Per Formula" (Wayback capture of 2026-03-07) ([EOBI, P](http://www.eobi.gov.pk/introduction/Pension.html)). That is one minimum for all EOBI pensions, not a survivor-only figure. A secondary source says the federal cabinet raised the minimum to Rs 11,500 from 1 January 2025 ([GoPunjab, S](https://gopunjab.pk/eobi-pension/)). The official page still shows Rs 10,000. Claims are filed at the regional office that covers the last insured employment ([LegalPK, S](https://legalpk.com/blog-post/eobi-pension-claim-process-pakistan)). LegalPK says a date of birth that does not match NADRA is the most common single cause of rejection. That is a blog's claim, not an official statistic. The survivor contribution minimum in the EOBI Act is unverified (source unreachable): the Pakistan Code page returns no text ([Pakistan Code, P](https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Nsa-sg-jjjjjjjjjjjjj.html)). GoPunjab says survivors need 36 months of insured work, which is unverified against the Act.

**The EOBI survivor's pension has no remarriage condition.** EOBI Act 1976 s.22B(1) says "the surviving spouse, if any, shall be entitled to a life pension". The s.22B text mentions marriage only for female children ([EOBI Act, Wayback capture 2023-12-03, P](https://web.archive.org/web/20231203162430/http://www.eobi.gov.pk/rules/eobilaw.html)). The Centre for Labour Research says of the survivor's pension: "It is not discontinued upon remarriage" ([CLR, S](https://clr.org.pk/docs/EOBI%20ACT%201976%20REALITY%20AND%20MYTH.pdf)). EOBI is a private-sector social-insurance scheme, not government family pension. The demo models government family pension only.

### 1.2 Rule v1, written fresh as a ZEN-ready JSON sketch

These are sketches of rule content, not engine syntax. Each rule returns `eligible`, `not_eligible` or `missing_info` plus a reason code. `not_eligible` goes to an officer, never to an automatic rejection. Where a clause is not federal or not primary, the sketch says so.

```json
{
  "ruleset": "federal-ordinary-family-pension",
  "version": "v1",
  "source": "Finance Division O.M. No. 1(13)-Reg.6/83 dated 23-10-1983, consolidated 'Updated as on 24.06.2024'",
  "effective_from": "1983-10-23",
  "effective_to": "2024-09-09",
  "rules": [
    {"id": "R1_widow_first", "when": {"relation": "widow", "deceased_sex": "male", "frc_links_claimant": true, "death_verified": true, "remarried": false}, "then": "eligible", "duration": "life", "basis": "para 8(2)(a)(i)"},
    {"id": "R1b_widow_remarriage", "when": {"relation": "widow", "remarried": true}, "then": "not_eligible", "reason": "WIDOW_REMARRIED", "handover": "next legal beneficiary draws from the remarriage date", "basis": "para 8(3)(c); para 8(5)"},
    {"id": "R2_share_split", "compute": "n = widows + eligible_children; if n <= 4 share = 1/n; else each widow 1/4, children split the balance", "basis": "Sindh rule 4.10 as quoted in SHC C.P. D-198/2025", "note": "federal multi-widow wording unverified; source text puts n = 4 in both branches, mock picks n <= 4"},
    {"id": "R3_son_age", "when": {"relation": "son", "age_gt": 21}, "then": "not_eligible", "reason": "CHILD_OVER_AGE", "basis": "para 8(2)(a)(ii), substituted 19-06-2018"},
    {"id": "R4_daughter_status", "when": {"relation": "daughter", "marital_status_in": ["unmarried", "widowed", "divorced"]}, "then": "eligible_until_marriage_or_remarriage", "basis": "para 8(2)(a)(ii)", "clause_since": "2018-06-19", "note": "federal text sets no divorce-timing condition"},
    {"id": "R5_required_docs", "require": ["death_certificate", "claimant_cnic", "frc", "nikah_nama_if_widow", "bank_title_equals_claimant"], "on_missing": "missing_info", "reason": "ASK_PROOF:<doc>", "basis": "EOBI and PASSCO forms, LegalPK; mock for government family pension"},
    {"id": "R6_single_pension", "when": {"already_draws_family_pension": true}, "then": "not_eligible", "reason": "SECOND_FAMILY_PENSION", "basis": "June 2024 draft notification only; mock rule"}
  ],
  "known_v1_caps": "some distant heirs (widow of a deceased son, grandchildren, widowed sister) were already limited to 10 years or the unexpired part of 10 years"
}
```

### 1.3 The real v1 to v2 change: the 10-year cap on heirs after the spouse

**v1: federal Ordinary Family Pension, rules in force until 09-09-2024** (O.M. No. 1(13)-Reg.6/83 dated 23-10-1983, as updated 24-06-2024) ([Finance Division, P](https://www.finance.gov.pk/circulars/circular_24062024.pdf)).
1. Widow: "Widow of the deceased for her life, if deceased is a male Government servant." It stops "in the event of her re-marriage", and the next heir draws from the date it stopped.
2. Failing a widow: shared equally by sons up to 21 and by unmarried, widowed or divorced daughters until marriage or remarriage. There is no overall time limit.
3. Some distant heirs (widow of a deceased son, grandchildren, widowed sister) were already limited to 10 years or the unexpired part of 10 years.

**v2: federal Ordinary Family Pension, from 10-09-2024** (O.M. F.No. 9(3)R-6/2024-264 dated 10-09-2024, signed by the Deputy Secretary (R-III) and addressed to "All Ministries/Divisions/CGA/AGPR/MAG"). It is based "on the recommendations of Pay and Pension Commission-2020" ([Finance Division OM, P](https://www.finance.gov.pk/circulars/circular_10092024_1.pdf); also enclosed in [AGP letter No. 1071/Estt-C/29-2008-I dated 27-11-2024, P](https://agp.gov.pk/SiteImage/Downloads/Family%20pension.pdf)). It amends the 1983 OM. Exact wording:
- "henceforth, Ordinary Family Pension, after the death or ineligibility of the spouse, shall be admissible to remaining entitled family members for a maximum period of 10 years"
- "In case of disabled/Special Children of a pensioner, the Ordinary Family Pension shall remain admissible for life of such children."
- For children: "Ordinary Family Pension shall remain admissible for 10 years or till the age of 21 years which so ever is later."
- "Existing instructions on the subject shall stand amended to the extent of above with immediate effect."

Two clarifications settle who is covered:
- O.M. No. F.9(3)-Reg.6/2024-300 dated 10-10-2024: "the decision does not apply to current family pensioners, as indicated by the use of the adverb "henceforth" in the ruling." It applies "to those who become eligible for family pension on or after the issuance" of the 10-09-2024 OM ([Finance Division, P](https://www.finance.gov.pk/circulars/circular_10102024_1.pdf)).
- O.M. No. F.9(3)/Reg.6/2024-264 dated 22-01-2025: the cap applies "to only those cases which have become entitled-to or whose family pension has started on or after 10.09.2024." Minor children remain "admissible till the age of 21 years as per eligibility criteria, priority and manner as prescribed" in the 1983 OM. **Where a widow is disqualified on or after 10-09-2024 and daughters then become eligible, the pension "shall remain admissible for the period of 10 or un-expired portion of 10 years only"** ([Finance Division, P](https://www.finance.gov.pk/circulars/circular_22012025.pdf)).

So the v2 rule reads as follows. The widow is unchanged: for life, and it stops on remarriage. After the spouse dies or becomes ineligible (including by remarriage), remaining eligible heirs draw for at most 10 years, or the unexpired part of 10 years. Children draw for 10 years or until 21, whichever is later. Disabled or special children draw for life. The cap applies only where entitlement starts on or after 10-09-2024. A widow drawing before that date is unaffected, but if she dies or remarries on or after 10-09-2024, the heir who takes over is capped.

Context, from secondary sources. The ECC approved the cap with the 2024-25 budget. Dawn reported civilian changes from 1 July 2024 and armed forces from FY 2025-26 ([Dawn, S](https://www.dawn.com/news/1842396)). The 1 July date was the ECC plan; the OM itself is dated 10-09-2024 "with immediate effect". A Business Recorder report of 27-06-2024 describes the **draft** notification ([Business Recorder, S, draft](https://www.brecorder.com/news/40310086)). Mettis Global (11-09-2024) and The News (19-10-2024) report the final rule and the exemption for existing family pensioners ([Mettis Global, S](https://mettisglobal.news/govt-fixes-family-pension-at-10-years-after-death/); [The News, S](https://www.thenews.com.pk/print/1241684-existing-family-pensioners-exempted-from-10-year-limit)). The 2025-26 budget speech was reported as saying family pensions "will now be limited to 10 years" after the spouse's death ([Dunya News, S](https://dunyanews.tv/en/Business/888779-budget-202526-family-pension-limited-to-10-years)). No Finance Act clause was found; the cap lives in an executive OM (unverified that no Finance Act mentions it). The Finance Division circular index lists only the 10-09-2024 OM and the two clarifications for Ordinary Family Pension, with no withdrawal or suspension ([Finance Division circulars, P](https://www.finance.gov.pk/circulars.html)). No court challenge to the federal cap was found (unverified that none exists).

Do not confuse it with the companion OM of the same number and date on **Special** Family Pension. That OM gives Shuhada heirs the pension "for 25 years after the death or ineligibility of spouse/first recipient" at a rate "enhanced to 50% of last drawn pension" ([Finance Division, P](https://www.finance.gov.pk/circulars/circular_10092024_3.pdf)). A circular of 03-01-2025 confirms it "is admissible to Shuhada of Armed Forces/Civil Armed Forces only" ([Finance Division, P](https://www.finance.gov.pk/circulars/circular_03012025.pdf)). That circular is about Special Family Pension and voluntary retirement. It does not support the Ordinary Family Pension grandfathering.

```json
{
  "ruleset": "federal-ordinary-family-pension",
  "version": "v2",
  "changes_from": "v1",
  "source": "Finance Division O.M. F.No. 9(3)R-6/2024-264 dated 10-09-2024",
  "clarified_by": ["O.M. No. F.9(3)-Reg.6/2024-300 dated 10-10-2024", "O.M. No. F.9(3)/Reg.6/2024-264 dated 22-01-2025"],
  "effective_from": "2024-09-10",
  "unchanged_from_v1": ["R1_widow_first", "R1b_widow_remarriage", "R2_share_split", "R3_son_age", "R4_daughter_status", "R5_required_docs", "R6_single_pension"],
  "new_rule": {
    "id": "R7_heir_10yr_cap",
    "applies_when": {"spouse_dead_or_ineligible": true, "claimant_is_spouse": false, "heir_entitlement_start_gte": "2024-09-10"},
    "limit": {"default": "10 years, or the un-expired portion of 10 years", "child": "max(10 years, until age 21)", "disabled_or_special_child": "life"},
    "clock_start": "ASSUMPTION: date of the spouse's death or ineligibility; not stated explicitly in the OMs",
    "grandfather": "family pension that started before 2024-09-10 stays on v1; a widow drawing before 2024-09-10 who dies or remarries on or after that date passes on a capped pension",
    "on_expired": "not_eligible",
    "reason": "HEIR_10YR_CAP"
  }
}
```

Engine test cases (from pass E):

| Case | Version | Result |
|---|---|---|
| Widow remarried in 2023, daughter took over in 2023 | v1 | No cap |
| Widow remarries in 2025, unmarried daughter aged 30 takes over | v2 | 10 years from takeover (clock start is our assumption) |
| Same, with a disabled son | v2 | For life |
| Widow drawing since 2015, alive and unmarried in 2026 | v1 and v2 | Unchanged |

**Alternative demo: Punjab, dramatic but unsettled.** Punjab changed its rule twice and a court then overrode it.
- To 01-12-2024: widow for life or until remarriage, then sons and daughters ([Punjab Finance, P](https://finance.punjab.gov.pk/system/files/CF28012022.pdf)).
- 02-12-2024, Notification No. FD.SR-III-4-244/2023(B): "A family pension sanctioned under this rule shall be restricted to the extent of spouse for a period of 10 years or till re-marriage, whichever is earlier". An issueless spouse gets it "for life or till re-marriage" ([Punjab Finance, P](https://finance.punjab.gov.pk/system/faqs/SR-III/widow%20for%2010%20years.pdf); [Punjab Gazette 10-12-2024, P](https://punjabcode.punjab.gov.pk/uploads/articles/178-of-2024-pdf.pdf)). A clarification of 30-05-2025 says it applies to those who "retire or die on or after 02.12.2024", and that after the spouse the "pension will not be transferable to any other family member" ([Punjab clarification, P](https://tevta.gop.pk/wp-content/uploads/2025/08/Clarification-Regarding-Amendments-in-the-punjab-Civil-Service-pension-Rules.pdf)).
- 20-08-2025, "with effect from 02-12-2024": "A family pension sanctioned under this rule shall be admissible to the extent of spouse for life or till re-marriage" ([Punjab Finance, P](https://finance.punjab.gov.pk/system/files/notification_20250820.pdf); [Punjab pension reforms page, P](https://finance.punjab.gov.pk/details/pension-reforms)).
- Lahore High Court, Zahida Yasmeen v. Govt. of the Punjab, 2026 LHC 8584, hearing 28-10-2026: both notifications declared "without lawful authority and of no legal effect only to the extent" they "exclude otherwise eligible members" of the family. Claims were sent back for a fresh decision within 60 days ([LHC, P](https://sys.lhc.gov.pk/appjudgments/2026LHC8584.pdf)). Appeal status is unverified.

This shows retroactive rule changes and a court override well. It is risky as a "current rule" because the law is in flux. Sindh reportedly restricted family pension in August 2025 to the widow or widower, children with disabilities, or parents for 10 years. That report is secondary, and the primary notification was not found (unverified) ([LinkedIn post by a Sindh officer, S](https://www.linkedin.com/posts/katiub_sindh-civil-servants-pension-rules-amendment-activity-7358873682720489473-U12h)).

**Backup change: divorced daughters (Sindh).** Supreme Court, Civil Petition No. 616-K of 2025, Province of Sindh v. Mst. Sorath Fatima, judgment by Ayesha A. Malik J, dated 10-07-2025 and reported 30-07-2025 ([Supreme Court judgment, P](https://scp.gov.pk/judgments/c.p._616_k_2025.pdf)). It struck down Sindh Finance Department Circular No. FD(PCDC)3(225)/2022 dated 05-12-2022. That circular made a divorced daughter eligible only if she was divorced when the pensioner died. The court held that the circular "is void ab initio, unconstitutional, and of no legal effect", and refused leave. Press reports say daughters are entitled whether the divorce came before or after the father's death, and cite Articles 9, 14, 25 and 27 ([Arab News, S](https://www.arabnews.pk/pakistan/divorced-daughters-entitled-to-fathers-pension-rules-pakistans-top-court-2610028); [The Nation, S](https://www.nation.com.pk/30-Jul-2025/divorced-daughters-entitled-to-father-s-pension-rules-sc); [Dunya News, S](https://dunyanews.tv/en/Pakistan/897634-divorced-daughters-entitled-to-fathers-pension-rules-sc)).

**Remarriage, narrowed.** Government family pension stops on a widow's remarriage:
- Federal: para 8(3)(c) of the 1983 OM ([Finance Division, P](https://www.finance.gov.pk/circulars/circular_24062024.pdf)).
- Punjab: the 1989 letter says "admissible to the widow for life or until re-marriage", and the 2024 and 2025 notifications re-enact cessation ([Punjab Finance, P](https://finance.punjab.gov.pk/system/files/CF28012022.pdf)).
- KP: rule 2(e) of the KP Civil Servants Pension Rules 2021, as quoted by the Peshawar High Court: "for life time or till re-marriage" ([PHC, P](https://www.peshawarhighcourt.gov.pk/PHCCMS//judgments/Said-Qamar.pdf)).
- Sindh: rule 4.10 of the 1963 rules, as quoted in SHC C.P. No. D-3212 of 2022 ([SHC, P](https://caselaw.shc.gov.pk/caselaw/view-file/MTk3NjM3Y2Ztcy1kYzgz)).
- The LHC upheld cessation in 2026 as gender-neutral: "The condition of cessation upon re-marriage therefore operates uniformly" (W.P. 633 of 2026, 2026 LHC 1547), and dismissed the appeal (ICA 101 of 2026, 2026 LHC 4262, 24-06-2026) ([LHC 1547, P](https://sys.lhc.gov.pk/appjudgments/2026LHC1547.pdf); [LHC 4262, P](https://sys.lhc.gov.pk/appjudgments/2026LHC4262.pdf)).

Two exceptions exist. The EOBI s.22B survivor pension has no remarriage condition (section 1.1). In Said Qamar (W.P. 1163-A/2023, announced 17-09-2025), the Peshawar High Court let a remarried **widower** keep a pension sanctioned in 2017, because the 2021 KP remarriage clause could not apply retrospectively ([PHC, P](https://www.peshawarhighcourt.gov.pk/PHCCMS//judgments/Said-Qamar.pdf)). The Supreme Court's Shaheen Yousaf case (2025 SCMR 1076) and the LHC's Zoya Islam case (2024 LHC 3944) protect remarried widows in **employment**, not pension ([Dawn, S](https://www.dawn.com/news/1906201); [Dawn, S](https://www.dawn.com/news/1860326/widow-cannot-be-sacked-from-job-after-second-marriage-lhc-rules)). No Federal Shariat Court ruling on widow remarriage and pension was found (unverified that none exists).

### 1.4 Where the notes conflict with team-repo/docs

`01-IDEA.md` step 11, `03-ARCHITECTURE.md` rule 4 ("must not have remarried (v1). v2 changes this") and the `05-DEMO-SCRIPT.md` button "Publish rule v2: Remarried widows stay eligible" all depend on a change that has no support. The v1 half of rule 4 is correct: a widow's government family pension stops on remarriage (section 1.3). The v2 half is not supported by any federal or provincial civil-service rule or ruling found as of 2026-11-21. A related gap: the idea doc's "an officer will check within 3 days" has no source. No official processing time was found. In SHC C.P. D-198/2025, the refusal letter was dated 18.10.2024 and the order 27.08.2025, about 10 months later. The court directed payment "within a period of one month" and cited the one-month limit in s.20 of the Sindh Civil Servants Act, 1973 ([SHC, P](https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz)). Keep "3 days" only as a mock service level.

### 1.5 Open risks a judge may raise

1. "Doesn't the Supreme Court protect remarried widows?" Shaheen Yousaf (2025 SCMR 1076) concerns compassionate employment, not pension. The LHC in 2026 (2026 LHC 1547; ICA 101/2026) expressly upheld pension cessation on remarriage as gender-neutral.
2. "EOBI widows keep their pension after remarriage." EOBI is a separate private-sector scheme, and s.22B grants the surviving spouse a "life pension". Answer: the demo models government family pension only.
3. "A remarried spouse kept a pension in KP." The PHC in 2025 (Said Qamar) protected a widower's pre-2021 pension only because the 2021 rule was not retrospective.
4. "When does the 10-year clock start for children?" The OM says the cap runs "after the death or ineligibility of the spouse", and the 22-01-2025 OM uses "un-expired portion of 10 years". It does not say explicitly whether a child's "10 years or till 21" also runs from the spouse's death. Treat the clock start as an assumption and say so.
5. "Does it apply to the armed forces?" Unconfirmed. The ordinary OM is copied to MAG, and Dawn reported armed forces from 2025-26, but no MoD instrument was found. The Special Family Pension (Shuhada) rule is different: 25 years at a 50% rate.
6. "Which daughters count?" Federal v1 includes unmarried, widowed and divorced daughters until marriage or remarriage (O.M. substitution of 19-06-2018). The SC voided Sindh's divorce-timing circular (CP 616-K/2025). The LHC voided Punjab's spouse-only rule in part (2026).
7. Date precision. The OM is dated 10-09-2024, "with immediate effect"; Dawn's 1 July date was the ECC plan, not the OM. The SC divorced-daughter judgment is dated 10-07-2025 and was reported 30-07-2025.
8. Absence claims ("no ruling", "no challenge", "no withdrawal") rest on searches of official sites and news, not on a complete case-law database.

### What we should build/do

Encode v1 from the federal 1983 OM as updated 24-06-2024, and v2 from the 10-09-2024 OM and its two clarifications, using the JSON above. Keep widow remarriage cessation as a real rule in both versions. It is sourced, not a mock field. Rewrite the three doc passages, and change the judge-console button to "Publish rule v2: 10-year cap for heirs after the spouse (OM 10-09-2024)". Seed the Digital Twin with about 5 past cases, including the four test cases above. Only cases where the heir's entitlement started on or after 2024-09-10 should change. Show the clock-start assumption in the officer view. Keep the shares rule visible in the officer view, so that a second widow who appears in the FRC is shown as a lawful co-sharer. The Punjab sequence can be an optional second demo, labelled "unsettled law".

## 2. Real pension fraud is mostly fake records, and claimant scams come second

Pakistan's documented losses come mostly from ghost pensioners, payments after death and record tampering, not from outsiders. **The Karachi Development Authority paid Rs667 million to 500 bogus pensioners even though the bank ran biometric checks every six months** ([Dawn, S](https://www.dawn.com/news/1904287/kda-paid-rs667m-to-500-bogus-pensioners-sindh-pac-finds)). **EOBI paid Rs2.79bn in old-age pension to 5,131 people whose ages had been changed.** EOBI said it had paid on matriculation-certificate DOBs, and announced that it would now pay on NADRA identity-card data ([The News, S](https://www.thenews.com.pk/print/1304620-pac-told-eobi-paid-rs2-79bn-to-over-5-000-fake-pensioners)). That is an announcement, not confirmed practice. In Sindh, "a fictitious woman was portrayed as the widow" and paid Rs4.3 million ([The Nation, S](https://www.nation.com.pk/01-Sep-2024/massive-pension-fund-fraud-uncovered-in-sindh-district-accounts-offices)). That is the real form of the prototype's fake-heir scenario. The AGP 2022-23 audit report on South Punjab local bodies mandates life certificates for pensioners and **no-remarriage certificates** for family pension cases ([Express Tribune, S](https://tribune.com.pk/story/2583170/audit-flags-financial-irregularities-worth-billions-in-southern-punjab)). A BISP audit found 12,078 government employees, pensioners and their spouses received Rs515.7m despite exclusion under a December 2019 cabinet decision (article dated 2026-11-08) ([Express Tribune, S](https://tribune.com.pk/story/2639218/bisp-audit-reveals-rs257-billion-irregularities)). Fake death certificates appear in a 2016 property case and a 2021 insurance case ([Daily Times, S](https://dailytimes.com.pk/78710/property-worth-billions-transferred-on-fake-death-certificates/); [ARY News, S](https://arynews.tv/fia-mother-faking-death-fake-insurance-children)). The notes found no Pakistani source on competing widows, payout-account takeover, or impersonation of AGPR.

### 2.1 Official channels: one sender rule, and it can be spoofed

BISP is the only body with a clear statement. **"All the BISP messages are sent from 8171 only", and the helpline is 0800-26477** ([APP, S](https://www.app.com.pk/national/bisp-cautions-citizens-about-fraudulent-messages-2/); [Geo, S](https://www.geo.tv/latest/545927-bisp-cautions-beneficiaries-against-fake-messages); [Radio Pakistan, S](https://radio.gov.pk/11-01-2024/people-warns-of-fraud-in-bisp-name)). APP says the dynamic survey "was free of charge". A bisp.gov.pk headline, seen only as a search snippet with no URL recorded, says there is no fee for the survey and messages from any other number are fraud (snippet only). Neither Geo nor APP says that every fee demand is fraud. In 2024, BISP and PTA discussed "strategies to combat the masking of messages and calls from 8171" (PID press release, 5 July 2024) ([PID, P](https://pid.gov.pk/site/press_detail/25791); [Express Tribune, S](https://tribune.com.pk/story/2477141)). PSCA says e-challans come only from 9915 with no payment links ([ProPakistani, S](https://propakistani.pk/2026/04/16/psca-warns-citizens-about-e-challan-sms-scam/)). PTA says no genuine courier asks for a verification code ([Profit, S](https://profit.pakistantoday.com.pk/2025/07/24/pta-warns-public-against-fake-courier-messages-seeking-verification-codes)). EOBI helplines are dated and conflicting: 08000-3624 in 2021 and 0800-3624 in 2016 ([Business Recorder, S](https://www.brecorder.com/news/40076165), now redirects, read from cache; [Express Tribune, S](https://tribune.com.pk/story/1162602/entertainment)). An unofficial site says to forward scam SMS to PTA on 9915. No PTA primary source was checked, and the "420" variant has no source ([scamcheck.tech, S](https://scamcheck.tech/scams/bisp-scam-pakistan)). No AGPR SMS sender was found. PECA offences are now handled by the NCCIA ([Wikipedia, S](https://en.wikipedia.org/wiki/National_Cyber_Crimes_Investigation_Agency)).

### 2.2 Global controls give concrete numbers to copy

The UK and US rely on death feeds and account checks. **UK State Pension fraud was 0.0% (£0m), with 0.1% (£190m) overpaid** (official error £110m, claimant error £80m), against 3.3% (£9.5bn) across all benefits in FYE 2025 ([GOV.UK, P](https://www.gov.uk/government/statistics/fraud-and-error-in-the-benefit-system-financial-year-2024-to-2025-estimates/fraud-and-error-in-the-benefit-system-financial-year-ending-fye-2025)). Tell Us Once can contact some public sector pension schemes so that they cancel future payments ([GOV.UK, P](https://www.gov.uk/after-a-death/organisations-you-need-to-contact-and-tell-us-once)). Its DWP wording was not re-checked. In the US, Treasury access to SSA's full Death Master File **prevented and recovered more than $31m in a five-month pilot** ([Treasury, P](https://home.treasury.gov/news/press-releases/jy2784)). In an older review, 68% of overpaid representative payees whose beneficiaries died were relatives ([SSA OIG, P](https://oig-files.ssa.gov/audits/full/html/96-61202.html), read via Wayback).

The thresholds conflict in places. SSA's 18 March 2025 press release moves all direct-deposit changes, in person and online, to **one business day**, and says online changes were previously held for 30 days ([SSA, P](https://www.ssa.gov/news/en/press/releases/2025-03-18.html)). The same-day SSA blog says changes made through my Social Security are "still subject to the 30-day hold" ([SSA blog, P](https://www.ssa.gov/blog/en/posts/2025-03-18.html)). Current practice was not confirmed. SSA said it planned to implement Treasury's Account Verification Service ([SSA blog, P](https://www.ssa.gov/blog/en/posts/2025-03-18.html)). Under UK guidance, a delay to a suspicious outbound payment "can last no longer than 4 business days". Firms need reasonable grounds to suspect fraud, the delay must last no longer than necessary, and firms must not routinely wait until the end of the fourth business day ([FCA FG24/6, P](https://fca.org.uk/publication/finalised-guidance/fg24-6.pdf)). Confirmation of Payee returns match, close match or no match ([UK Finance, S](https://www.ukfinance.org.uk/news-and-insight/blogs/changing-name-game-confirmation-payee), read via Wayback). It does not stop payments, and money sent to the wrong account may not be recoverable ([Virgin Money, S](https://uk.virginmoney.com/service/cop/)). The PSR says CoP covers more than 99% of Faster Payments, with over 2 million checks a day ([PSR, P](https://www.psr.org.uk/news-and-updates/latest-news/news/fraud-prevention-is-key-during-international-fraud-awareness-week/)). No Pakistani cooling-off period for changing a payout account was found.

### What we should build/do

Keep SafeSwitch's 48h hold with PIN or voice confirmation. Describe it as sitting between SSA's stated one-business-day processing and the UK's 4-business-day maximum. When a red flag fires, allow the hold to run up to 4 business days and release it as soon as an officer clears the flag. Red flags: an account used by another claim, a payee close match or no match, or a change soon after the death is reported. This follows the FCA line that a delay lasts no longer than necessary. Add a mock CoP call before every payout, mapping match to AUTO, close match to ASK_PROOF and no match to UNSURE. Use NADRA CNIC DOB as the single source of truth, following EOBI's announced fix. Add an "already drawing or excluded" cross-check, and a family-record check that separates a lawful second widow from a fictitious one. In Scam Shield, weight fee, code, link and unverified-payment rules above the sender ID. Show real short codes in the README as real-world patterns only, and use mock senders in the app. Put the KDA case on a slide: periodic biometrics alone did not stop Rs667m in losses.

## 3. Name matching must lean on CNIC, because "Muhammad" carries almost no evidence

Pakistani names vary by transliteration (Mohammad vs Muhammad). Male names may be "in any order", may carry a prefixed caste name, and do not always include the family name. Female names also appear in any order. A woman may use her father's personal name as a surname and later her husband's ([GOV.UK Pakistan profile, P](https://www.gov.uk/government/publications/pakistan-knowledge-base-profile/pakistan-knowledge-base-profile)). The CNIC has a mandatory father's/husband's-name field ([Dawn, S](https://www.dawn.com/news/1652563)). Wikipedia still describes it as the husband's name for married women, which is out of date ([Wikipedia: CNIC, S](https://en.wikipedia.org/wiki/CNIC_(Pakistan))). Since October 2021, NADRA lets married women choose to keep their father's name there, as announced by the NADRA chairman; no NADRA circular was found ([Dawn, S](https://www.dawn.com/news/1652563)). So **Zainab's CNIC may not name Aslam at all**, and a mismatch in that field must count as weak evidence. As of May 2024 the passport authority required the husband's name and was considering a change ([Arab News PK, S](https://www.arabnews.pk/node/2516036)).

In one informal Arabic-name test, a Levenshtein-based ratio (fuzzywuzzy) with a threshold of 75 gave 88% accuracy on 50 names. It missed "Mohamad"/"Muhammed" (score 67) and falsely matched "Wesam"/"Esam" (89). **Soundex and Double Metaphone mapped seven distinct names (Hasan, Hussam and others) to a single code** ([WS-DL blog, S](https://ws-dl.blogspot.com/2020/12/2020-12-28-tools-and-libraries-for.html)). rapidfuzz's `token_sort_ratio` ignores word order. `token_set_ratio` returns 100 when one name is a subset of the other ([RapidFuzz, P](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html)), which is too permissive for payouts ("Aslam" vs "Muhammad Aslam"). Splink's Fellegi-Sunter guide sums log2(m/u) per field and uses term-frequency adjustment so that common values such as "Muhammad" weigh less ([Splink, P](https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html); [Splink TF, P](https://moj-analytical-services.github.io/splink/topic_guides/comparisons/term-frequency.html)). OFAC sets no threshold and leaves the choice to the screener ([OFAC, P](https://ofac.treasury.gov/faqs/topic/1636)). Unlike sanctions screening, which often has only a name, this pipeline can lean on ID numbers and birth dates ([OpenSanctions, S](https://www.opensanctions.org/articles/2025-06-24-name-matching.md)).

| Stage | Design (thresholds are proposals to tune, not cited values) |
|---|---|
| Parse | Split on s/o, w/o, d/o, bin, bint, ibn. Strip honorifics (Syed, Sheikh, Haji, Chaudhry, Malik, Begum, Bibi, Mst) into a low-weight field. This Pakistani list beyond GOV.UK's titles is unverified and comes from domain knowledge. |
| Canonicalise | Mohd, Md, M., Mohammad, Mohammed and Muhammed all map to `muhammad`. Expand "M." only when the other record has a Muhammad-family token. |
| Block | CNIC exact, OR key token plus birth year, OR phonetic key plus district. Phonetic codes are used only to propose pairs. |
| Score | Name `token_sort_ratio` with Muhammad down-weighted, in bands >=95 / 85-95 / 70-85 / <70. CNIC exact / one-digit typo / different / missing. DOB exact / year / ±1 / different / missing. |
| Route | p >= 0.95, CNIC exact and no flag: auto-match. 0.70-0.95: ask for the missing field. Below 0.70, a CNIC conflict, or two candidates above 0.70: UNSURE. **No auto-match without an exact CNIC.** Never auto-reject. |

For synthetic evaluation, generate seeded identities and corrupt them with transliteration swaps, abbreviations, reordering, dropped family names, added or removed honorifics, s/o vs w/o swaps, CNIC and DOB OCR digit errors, and missing DOB. Add hard negatives: a second person with the same full name, same name and birth year, siblings, and a CNIC one digit off. Report the false-match rate, false non-match rate, UNSURE rate and blocking recall, and plot them against the threshold. The WS-DL design of many names times many variants, compared pairwise, is a usable template ([WS-DL, S](https://ws-dl.blogspot.com/2020/12/2020-12-28-tools-and-libraries-for.html)). Results will not reflect real NADRA error rates, so state that as a limit.

### What we should build/do

Build the five-stage pipeline exactly as in the table, with field levels and weights saved into the auditor trace. Generate about 500 identities with variants and hard negatives, including the seeded second Muhammad Aslam. Set the auto-match threshold where the false-match rate on hard negatives is 0, then check that 0.95 still holds. Show both curves on the evaluation page. Do not use `token_set_ratio` or phonetic codes as match evidence.

## 4. Forgery checks are weak signals and must be shown that way

No single cheap method is reliable on phone photos of documents. ELA highlights regions with a different JPEG history, but a change raises every 8x8 block it touches, and a repeatedly resaved image ends in a black ELA picture ([FotoForensics, P](https://fotoforensics.com/tutorial-ela.php)). Its originator said "It is up to the user to interpret the results" ([Wikipedia, S](https://en.wikipedia.org/wiki/Error_level_analysis)). Classical methods, ELA among them, weaken under compression, noise and scaling ([IIETA, P](https://iieta.org/download/file/fid/192306)). **In document benchmarks, median tampered area is only 0.27% to 0.97% of pixels in four datasets** (2.88-4.17% in two others), and camera-sensor noise cues find few useful signals in scanned or synthetic documents ([DocForge-Bench, P](https://arxiv.org/html/2603.01433v1)). In a 2025 study, WhatsApp chat (image-mode) transfers removed timestamp, location, device and thumbnail EXIF, while document-mode transfers kept all fields ([SciEPublish, P](https://www.sciepublish.com/article/pii/567)). So **missing EXIF is normal and must not count against the applicant**.

Tesseract ships an official Urdu model ([Tesseract data files, P](https://tesseract-ocr.github.io/tessdoc/Data-Files.html)), but no accuracy figure for Nastaliq or for photographed certificates was found. The CNIC has 13 digits ([Wikipedia, S](https://en.wikipedia.org/wiki/CNIC_(Pakistan))). The OECD TIN sheet writes the template as XXXX-XXXXXX-X, while Wikipedia uses 5-7-1. OECD's own breakdown (5 location, 7 family, 1 last digit) matches 5-7-1, so the conflict is in OECD's template string only ([OECD, P](https://www.oecd.org/content/dam/oecd/en/topics/policy-issue-focus/aeoi/pakistan-tin.pdf)). The OECD sheet and Wikipedia both state odd last digit = male and even = female. No NADRA primary source confirms it. A 2015 review found keypoint copy-move detection (SIFT or ORB) better than block methods in efficiency and robustness to rotation and scaling ([Semantic Scholar, P](https://www.semanticscholar.org/paper/7f0e9d3ed7eaa3a951534033200d168652f26986)). Our inference, with no source, is that repeated text glyphs will cause false matches, which limits it to seals and stamps. SIFT moved to the main OpenCV repository in 4.4.0 ([OpenCV 4.4.0, P](https://opencv.org/opencv-4-4-0/), snippet only). We found no public dataset of forged Pakistani certificates. DocTamper's 170,000 images are synthetic ([CVPR 2023, P](https://openaccess.thecvf.com/content/CVPR2023/papers/Qu_Towards_Robust_Tampered_Text_Detection_in_Document_Image_New_Dataset_CVPR_2023_paper.pdf)).

**QR verification is not confirmed.** NADRA's page says the provincial CRMS issues birth, death, marriage and divorce certificates across 11,000+ Union Councils, but it does not mention QR codes ([NADRA ecosystem, P](https://www.nadra.gov.pk/ecosystem)). The QR claim appears only on a law-firm marketing page and an unofficial aggregator ([Right Law, S](https://rightlaw.com.pk/nadra-certificates-in-pakistan-marriage-divorce-birth-death-certificates/); [trackingidcheckonline.pk, S](https://trackingidcheckonline.pk/nadra-death-certificate-online-check/)). Automation-bias research says reviewers over-rely on automated output, and that bias can be reduced by "providing supportive information rather than commands" ([Goddard et al., P](https://pmc.ncbi.nlm.nih.gov/articles/PMC3240751/); [CSET, S](https://cset.georgetown.edu/publication/ai-safety-and-automation-bias/)).

### What we should build/do

Rank checks by evidence: (1) OCR format and registry cross-check by CNIC and DOB; (2) copy-move limited to seal regions, with a match count tuned on mock images; (3) ELA on the original upload, shown next to the image; (4) EXIF recorded as context only; (5) optional QR decode, where "no QR found" is a neutral state. Show a list of indicators, each with evidence and a "what this cannot tell" line, using labels like "needs a second look", and never "fake". Do not roll them into a single forgery score. Log officer disagreement for the evaluation page. Build a labelled mock set with each image in original, WhatsApp-recompressed and screenshot form. The team docs never claim QR verification. Keep it that way, and add a line to `02-COMPLIANCE.md` "honest limits" that QR verification is not built.

## 5. Low-literacy design means voice on every screen and a 170 KB shell

Microsoft Research India's text-free interfaces were tested with illiterate domestic labourers, with a focus on women, in three Bangalore slums. Subjects recognised semi-abstract cartoons and photo-realistic graphics much better than complex abstract graphics, and could easily recognise numerals ([Medhi et al., ICTD 2006, P](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/medhi_ictd2006.pdf)). A 2022 MSR paper cites prior HCI and ICTD studies finding text interfaces unusable for low-literate users ([COMPASS 2022, S for this claim](https://www.microsoft.com/en-us/research/wp-content/uploads/2022/05/compass22-34-taps.pdf)). Pakistan's voice services prove reach: **Polly drew 165,000 users and 636,000 interactions in about a year** ([Raza et al., S](https://aghaaliraza.com/papers/2013-behavior-analysis-of-low-literate-users-of.html)). Shared, intermediated phone use is normal for South Asian women ([Sambasivan et al., SOUPS 2018, P](https://www.usenix.org/system/files/conference/soups2018/soups2018-sambasivan.pdf)), which makes Helper Mode the default case. **Pakistan has 81% mobile broadband coverage but only 29% mobile internet use** ([GSMA, P](https://www.gsma.com/newsroom/press-release/unlocking-pakistans-digital-future-gsma-highlights-opportunities-and-progress-at-digital-nation-summit-islamabad/)).

Azure has ur-PK neural voices, UzmaNeural and AsadNeural ([Microsoft Q&A, S](https://learn.microsoft.com/en-us/answers/questions/5921704/urdu-as-support-voice-typing)). Azure neural TTS includes **0.5M characters free per month** ([Azure pricing, P](https://azure.microsoft.com/en-us/pricing/details/speech/)). The pay-as-you-go rate (reported as about $15 per 1M characters) did not show in the scrape, because the page loads prices by region, so it is unverified. Google lists only ur-IN voices ([Google, P](https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types)). Azure speech-to-text lists Urdu as ur-IN, and no ur-PK STT locale was found ([Azure language support, P](https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=stt)). Whisper-small Urdu WER ranges from 41 to 56 untuned and 27 to 33 fine-tuned across three test sets ([arXiv 2409.11252, P](https://arxiv.org/html/2409.11252v3)), so every value filled by voice needs a tap to confirm. web.dev's slow-3G budget for critical-path resources is **about 170 KB total (JS 100 KB) with a TTI budget of 5 s** ([web.dev, P](https://web.dev/articles/your-first-performance-budget)). Background Sync works only in Chromium browsers, and not in Android WebView, Firefox or Safari ([MDN, P](https://developer.mozilla.org/en-US/docs/Web/API/Background_Synchronization_API)). The Idempotency-Key header is an IETF draft (version -08, 22 October 2026), not an RFC. It uses 409 while a request is still being processed and 422 for a reused key with a different payload ([IETF, P](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header)). `navigator.storage.persist()` protects IndexedDB from eviction ([web.dev, P](https://web.dev/articles/persistent-storage)). Dexie details were not checked against current docs.

### What we should build/do

Budget the citizen shell at 170 KB or less (JS 100 KB or less), each later screen at 30 KB or less, each audio clip at about 15 KB or less, and photos compressed on the device to about 200 KB. These are our own numbers, derived from web.dev. Pre-generate about 60 prompts with UzmaNeural (about 6,000 characters, well inside the free tier), and build dynamic reasons from cached clips per reason code. Create the outbox key as a UUID when the user taps save. Flush on `sync`, app open, the `online` event, and a "Send now" button. The server keeps a unique key per principal, replays the stored response, returns 422 for a reused key with a different body and 409 while a request is in flight. Partition the outbox by family in Helper Mode. Send payout confirmations to the widow directly, never to the helper's phone. A mock "call to hear status" IVR line is a cheap extra.

## 6. Jev reads small facts from text and images, and code decides

Images and Box on jev-1.14.0 (released 2026-10-14) are "dreamer-ready", not production ([Changelog, P](https://docs.typesafe.ai/changelog.md)). They require the `TypeSafe-Danger-Zone-Images: true` header, or the request returns 400 ([Images, P](https://docs.typesafe.ai/images.md); [Box, P](https://docs.typesafe.ai/primitives/box.md)). Images also work on Jev 1.13; Box needs 1.14. The limits are strict: **PNG or JPEG only, 16 MiB per file, each side 280-1568 px, 78,400-2,458,624 total pixels, 32 MiB per request. Out-of-range images are "rejected, never resized", and the whole request fails.** The API strips EXIF without applying its orientation, so rotate the pixels before sending. Use a fresh UUID reference for each image, and put a shared image in `state` once ([Images, P](https://docs.typesafe.ai/images.md)). Box returns fractional coordinates plus a confidence, has no recommended threshold (the example uses 0.6), and **"A Box answer is always a box"**. It must therefore be paired with a presence Noul ([Box, P](https://docs.typesafe.ai/primitives/box.md)).

In the scanned-record cookbook, rabies vaccines on the page scored 0.97 or more and look-alikes 0.02 or less. A covered date came back `unreadable` with legibility 0.05. A combined question missed two doses, and you could not tell whether the date was misread or misjudged, so the cookbook splits reading from judging ([Reading scanned documents, P](https://docs.typesafe.ai/cookbooks/reading_scanned_documents.md)). In the OCR cookbook, a page check plus a crop check, flagging when either is below 0.25, caught all 3 misreads among 15 fields; neither check alone caught all three. The same cookbook uses a 120 s timeout ([OCR confidence, P](https://docs.typesafe.ai/cookbooks/ocr_confidence_bounding_boxes.md)). These samples are anecdotal. A Choice "always picks an option": a lamp complaint scored 0.96 on a product while its companion Noul read 0.02. The source uses 0.7 thresholds and sends a Noul below 0.3 to a general inbox. Our design choice is simpler: **read a Choice only when the companion Noul is above 0.7 and the top choice is above 0.7, and send everything else to a person** ([Companion Noul, P](https://docs.typesafe.ai/patterns/companion-noul.md)). Images cost the normal per-token input price, with no estimator yet. Image latency is unpublished ([Images, P](https://docs.typesafe.ai/images.md)). None of the pages we read claims tamper detection or Urdu reading. A Choice accepts up to 255 options; that page still recommends an `other` option, while the companion-Noul page argues against it ([Choice, P](https://docs.typesafe.ai/primitives/choice.md)).

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

The research moves the prototype from plausible to grounded in one respect that judges can check. The pension rules, v1 and v2, now trace to dated primary Finance Division OMs, and the holds and thresholds trace to published foreign controls or are labelled as our own choices. The remarried-widow example was the one piece of story that would fail a fact check: every civil-service rule found stops a widow's family pension on remarriage, and the LHC upheld that in 2026. The 10-year cap replaces it with a better demo. Its grandfather clause, settled by the 10-10-2024 and 22-01-2025 OMs, gives the Digital Twin a real reason to show "decided under v1". The one open point is when the 10-year clock starts, and the demo should say it is an assumption. The deeper finding is that Pakistan's largest documented losses came from fake records that passed periodic checks, not from clever outsiders. That makes registry cross-matching on CNIC and DOB more central to the pitch than any image forensics. Forensics, the Jev document questions and the scam sensors are honest only when presented as indicators with published limits.

## Sources

P = primary (government, court, regulator, official form, vendor's own docs, original paper). S = secondary (news, blog, social, third-party summary).

| URL | Type | What it supports |
|---|---|---|
| https://www.finance.gov.pk/circulars/circular_10092024_1.pdf | P | v2: OM F.No. 9(3)R-6/2024-264 dated 10-09-2024, 10-year cap wording (Wayback copy 20260218 also works) |
| https://www.finance.gov.pk/circulars/circular_10102024_1.pdf | P | Clarification 10-10-2024: does not apply to current family pensioners |
| https://www.finance.gov.pk/circulars/circular_22012025.pdf | P | Clarification 22-01-2025: scope from 10.09.2024, "un-expired portion of 10 years" |
| https://www.finance.gov.pk/circulars/circular_24062024.pdf | P | v1: 1983 OM consolidated 24.06.2024; widow for life, remarriage bar para 8(3)(c), children to 21, daughters |
| https://www.finance.gov.pk/circulars/circular_23101983.pdf | P | Original O.M. No. 1(13)-Reg.6/83 dated 23-10-1983 |
| https://www.finance.gov.pk/circulars/circular_10092024_3.pdf | P | Companion Special Family Pension OM (Shuhada, 25 years, 50%) |
| https://www.finance.gov.pk/circulars/circular_03012025.pdf | P | Special Family Pension for Shuhada only; not the ordinary cap |
| https://www.finance.gov.pk/circulars.html | P | Circular index: no withdrawal of the cap |
| https://agp.gov.pk/SiteImage/Downloads/Family%20pension.pdf | P | AGP letter of 27-11-2024 enclosing the 10-09-2024 OM |
| https://caselaw.shc.gov.pk/caselaw/view-file/Mjc4NjY3Y2Ztcy1kYzgz | P | SHC C.P. D-198/2025 (27.08.2025): Sindh rule 4.10 text, share split, succession, daughters till remarriage, 10-month delay, one-month direction |
| https://caselaw.shc.gov.pk/caselaw/view-file/MTk3NjM3Y2Ztcy1kYzgz | P | SHC C.P. D-3212/2022: Sindh widow remarriage bar |
| https://scp.gov.pk/judgments/c.p._616_k_2025.pdf | P | SC CP 616-K/2025, judgment 10-07-2025: Sindh circular of 05-12-2022 void |
| https://finance.punjab.gov.pk/system/files/CF28012022.pdf | P | Punjab 1989 and 2013 letters: widow for life or until remarriage |
| https://finance.punjab.gov.pk/system/faqs/SR-III/widow%20for%2010%20years.pdf | P | Punjab notification 02-12-2024: spouse only, 10 years or remarriage |
| https://punjabcode.punjab.gov.pk/uploads/articles/178-of-2024-pdf.pdf | P | Punjab Gazette 10-12-2024 copy of the same notification |
| https://finance.punjab.gov.pk/system/files/notification_20250820.pdf | P | Punjab notification 20-08-2025, retroactive to 02-12-2024: spouse for life or remarriage |
| https://tevta.gop.pk/wp-content/uploads/2025/08/Clarification-Regarding-Amendments-in-the-punjab-Civil-Service-pension-Rules.pdf | P | Punjab clarification 30-05-2025: scope, not transferable |
| https://finance.punjab.gov.pk/details/pension-reforms | P | Punjab: family pension restricted to the spouse |
| https://sys.lhc.gov.pk/appjudgments/2026LHC8584.pdf | P | LHC 2026 LHC 8584: Punjab notifications void to the extent they exclude eligible members |
| https://sys.lhc.gov.pk/appjudgments/2026LHC1547.pdf | P | LHC 2026: remarriage cessation upheld as gender-neutral |
| https://sys.lhc.gov.pk/appjudgments/2026LHC4262.pdf | P | LHC ICA 101/2026: appeal dismissed |
| https://www.peshawarhighcourt.gov.pk/PHCCMS//judgments/Said-Qamar.pdf | P | KP rule 2(e) remarriage bar; widower exception (non-retrospectivity) |
| https://web.archive.org/web/20231203162430/http://www.eobi.gov.pk/rules/eobilaw.html | P | EOBI Act s.22B "life pension", no remarriage condition |
| https://clr.org.pk/docs/EOBI%20ACT%201976%20REALITY%20AND%20MYTH.pdf | S | EOBI survivor pension not discontinued on remarriage |
| https://www.dawn.com/news/1842396 | S | ECC approval with 2024-25 budget; armed forces from 2025-26 |
| https://dunyanews.tv/en/Business/888779-budget-202526-family-pension-limited-to-10-years | S | 2025-26 budget speech on the cap |
| https://www.dawn.com/news/1906201 | S | Shaheen Yousaf (2025 SCMR 1076): employment, not pension |
| https://www.dawn.com/news/1860326/widow-cannot-be-sacked-from-job-after-second-marriage-lhc-rules | S | Zoya Islam (2024 LHC 3944): employment, not pension |
| https://www.linkedin.com/posts/katiub_sindh-civil-servants-pension-rules-amendment-activity-7358873682720489473-U12h | S | Reported Sindh August 2025 restriction (primary not found, unverified) |
| https://www.brecorder.com/news/40310086 | S | June 2024 draft notification: cap wording, one-pension rule (draft only) |
| https://mettisglobal.news/govt-fixes-family-pension-at-10-years-after-death/ | S | Final cap reported 11-09-2024, child to 21 |
| https://www.thenews.com.pk/print/1241684-existing-family-pensioners-exempted-from-10-year-limit | S | Existing pensioners exempt (reported) |
| https://www.arabnews.pk/pakistan/divorced-daughters-entitled-to-fathers-pension-rules-pakistans-top-court-2610028 | S | SC divorced-daughter ruling, reported 30-07-2025 |
| https://www.nation.com.pk/30-Jul-2025/divorced-daughters-entitled-to-father-s-pension-rules-sc | S | Same ruling; 2022 Sindh circular |
| https://dunyanews.tv/en/Pakistan/897634-divorced-daughters-entitled-to-fathers-pension-rules-sc | S | Same ruling; Articles 9, 14, 25, 27 |
| https://legalpk.com/blog-post/eobi-pension-claim-process-pakistan | S | EOBI documents, regional office, DOB mismatch (blog claim) |
| https://www.passco.gov.pk/wp-content/uploads/2023/11/Widow-Pension-Form.pdf | P | "Death certificate issued by Municipality", indemnity bond |
| http://www.eobi.gov.pk/announcement/Pension-Account/Survivor-form.pdf | P | EOBI survivor form: indemnity bond, Grade-17 attested nikah nama (live host dead; read via Wayback 2023-12-03) |
| http://www.eobi.gov.pk/introduction/Pension.html | P | EOBI minimum Rs 10,000 (read via Wayback 2026-03-07) |
| https://gopunjab.pk/eobi-pension/ | S | Rs 11,500 minimum from 1 January 2025 |
| https://pakistancode.gov.pk/english/UY2FqaJw1-apaUY2Fqa-apaUY2Nsa-sg-jjjjjjjjjjjjj.html | P | EOBI Act (unreachable: page returns no text) |
| https://www.dawn.com/news/1904287/kda-paid-rs667m-to-500-bogus-pensioners-sindh-pac-finds | S | KDA Rs667m, 6-month biometrics |
| https://www.thenews.com.pk/print/1304620-pac-told-eobi-paid-rs2-79bn-to-over-5-000-fake-pensioners | S | EOBI Rs2.79bn, matric DOBs, announced NADRA fix |
| https://www.nation.com.pk/01-Sep-2024/massive-pension-fund-fraud-uncovered-in-sindh-district-accounts-offices | S | Fictitious widow, Rs4.3m |
| https://tribune.com.pk/story/2583170/audit-flags-financial-irregularities-worth-billions-in-southern-punjab | S | AGP audit: life and no-remarriage certificates |
| https://tribune.com.pk/story/2639218/bisp-audit-reveals-rs257-billion-irregularities | S | BISP excluded employees and pensioners paid |
| https://dailytimes.com.pk/78710/property-worth-billions-transferred-on-fake-death-certificates/ | S | Fake death certificates, property (2016) |
| https://arynews.tv/fia-mother-faking-death-fake-insurance-children | S | Fake death certificate, insurance (2021) |
| https://www.app.com.pk/national/bisp-cautions-citizens-about-fraudulent-messages-2/ | S | BISP 8171 only, helpline, survey free |
| https://www.geo.tv/latest/545927-bisp-cautions-beneficiaries-against-fake-messages | S | BISP 8171, helpline |
| https://radio.gov.pk/11-01-2024/people-warns-of-fraud-in-bisp-name | S | BISP 8171 only, helpline |
| https://pid.gov.pk/site/press_detail/25791 | P | BISP and PTA on masking of 8171 (5 July 2024) |
| https://tribune.com.pk/story/2477141 | S | Same masking report |
| https://propakistani.pk/2026/04/16/psca-warns-citizens-about-e-challan-sms-scam/ | S | PSCA 9915, no links |
| https://profit.pakistantoday.com.pk/2025/07/24/pta-warns-public-against-fake-courier-messages-seeking-verification-codes | S | No verification codes |
| https://www.brecorder.com/news/40076165 | S | EOBI helpline 08000-3624 (2021; URL now redirects) |
| https://tribune.com.pk/story/1162602/entertainment | S | EOBI helpline 0800-3624 (2016) |
| https://scamcheck.tech/scams/bisp-scam-pakistan | S | Forward scam SMS to 9915 (unofficial) |
| https://en.wikipedia.org/wiki/National_Cyber_Crimes_Investigation_Agency | S | NCCIA handles PECA |
| https://www.gov.uk/government/statistics/fraud-and-error-in-the-benefit-system-financial-year-2024-to-2025-estimates/fraud-and-error-in-the-benefit-system-financial-year-ending-fye-2025 | P | DWP rates, State Pension 0.0% fraud |
| https://www.gov.uk/after-a-death/organisations-you-need-to-contact-and-tell-us-once | P | Tell Us Once and public sector pension schemes |
| https://home.treasury.gov/news/press-releases/jy2784 | P | Death file pilot, $31m |
| https://oig-files.ssa.gov/audits/full/html/96-61202.html | P | 68% of overpaid representative payees were relatives (read via Wayback) |
| https://www.ssa.gov/news/en/press/releases/2025-03-18.html | P | One-business-day direct-deposit change |
| https://www.ssa.gov/blog/en/posts/2025-03-18.html | P | 30-day hold for my Social Security; AVS planned |
| https://fca.org.uk/publication/finalised-guidance/fg24-6.pdf | P | 4-business-day maximum delay; no routine full wait |
| https://www.ukfinance.org.uk/news-and-insight/blogs/changing-name-game-confirmation-payee | S | CoP outcomes (read via Wayback) |
| https://uk.virginmoney.com/service/cop/ | S | CoP does not stop payments |
| https://www.psr.org.uk/news-and-updates/latest-news/news/fraud-prevention-is-key-during-international-fraud-awareness-week/ | P | CoP covers >99% of Faster Payments, >2 million checks a day |
| https://www.gov.uk/government/publications/pakistan-knowledge-base-profile/pakistan-knowledge-base-profile | P | Pakistani name structure, titles |
| https://en.wikipedia.org/wiki/CNIC_(Pakistan) | S | 13-digit CNIC; father/husband field (out of date for married women) |
| https://www.dawn.com/news/1652563 | S | NADRA 2021 father's-name option; mandatory field |
| https://www.arabnews.pk/node/2516036 | S | Passport husband's-name requirement as of May 2024 |
| https://ws-dl.blogspot.com/2020/12/2020-12-28-tools-and-libraries-for.html | S | Arabic name test, phonetic over-merging, evaluation template |
| https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html | P | token_sort and token_set behaviour |
| https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html | P | Fellegi-Sunter weights |
| https://moj-analytical-services.github.io/splink/topic_guides/comparisons/term-frequency.html | P | Term-frequency adjustment |
| https://ofac.treasury.gov/faqs/topic/1636 | P | No fixed OFAC threshold |
| https://www.opensanctions.org/articles/2025-06-24-name-matching.md | S | Sanctions screening often has only a name |
| https://fotoforensics.com/tutorial-ela.php | P | ELA method and caveats |
| https://en.wikipedia.org/wiki/Error_level_analysis | S | Krawetz quote |
| https://iieta.org/download/file/fid/192306 | P | Classical methods degrade under post-processing |
| https://arxiv.org/html/2603.01433v1 | P | Tampered-area fractions, sensor-noise limits |
| https://www.sciepublish.com/article/pii/567 | P | WhatsApp chat transfers remove most EXIF |
| https://tesseract-ocr.github.io/tessdoc/Data-Files.html | P | Tesseract Urdu model |
| https://www.oecd.org/content/dam/oecd/en/topics/policy-issue-focus/aeoi/pakistan-tin.pdf | P | CNIC structure, template conflict, gender digit |
| https://www.semanticscholar.org/paper/7f0e9d3ed7eaa3a951534033200d168652f26986 | P | Keypoint copy-move review |
| https://opencv.org/opencv-4-4-0/ | P | SIFT moved to main OpenCV in 4.4.0 (snippet only) |
| https://openaccess.thecvf.com/content/CVPR2023/papers/Qu_Towards_Robust_Tampered_Text_Detection_in_Document_Image_New_Dataset_CVPR_2023_paper.pdf | P | DocTamper dataset |
| https://www.nadra.gov.pk/ecosystem | P | CRMS certificates, no QR mention |
| https://rightlaw.com.pk/nadra-certificates-in-pakistan-marriage-divorce-birth-death-certificates/ | S | QR claim (commercial, unconfirmed) |
| https://trackingidcheckonline.pk/nadra-death-certificate-online-check/ | S | QR claim (unofficial, unconfirmed) |
| https://pmc.ncbi.nlm.nih.gov/articles/PMC3240751/ | P | Automation bias mitigation |
| https://cset.georgetown.edu/publication/ai-safety-and-automation-bias/ | S | Over-reliance on automated systems |
| https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/medhi_ictd2006.pdf | P | Text-free UI study, cartoons, numerals |
| https://www.microsoft.com/en-us/research/wp-content/uploads/2022/05/compass22-34-taps.pdf | S | Cites prior work: text UIs unusable for low-literate users |
| https://aghaaliraza.com/papers/2013-behavior-analysis-of-low-literate-users-of.html | S | Polly reach in Pakistan |
| https://www.usenix.org/system/files/conference/soups2018/soups2018-sambasivan.pdf | P | Shared phones, intermediated use |
| https://www.gsma.com/newsroom/press-release/unlocking-pakistans-digital-future-gsma-highlights-opportunities-and-progress-at-digital-nation-summit-islamabad/ | P | 81% coverage, 29% use |
| https://learn.microsoft.com/en-us/answers/questions/5921704/urdu-as-support-voice-typing | S | ur-PK Azure voices |
| https://learn.microsoft.com/azure/ai-services/speech-service/language-support?tabs=stt | P | Azure STT Urdu is ur-IN only |
| https://azure.microsoft.com/en-us/pricing/details/speech/ | P | TTS free tier (pay-as-you-go rate unverified) |
| https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types | P | Google only ur-IN |
| https://arxiv.org/html/2409.11252v3 | P | Urdu Whisper WER |
| https://web.dev/articles/your-first-performance-budget | P | 170 KB slow-3G budget |
| https://developer.mozilla.org/en-US/docs/Web/API/Background_Synchronization_API | P | Background Sync support |
| https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header | P | Idempotency-Key draft -08, 409 and 422 |
| https://web.dev/articles/persistent-storage | P | Persistent storage |
| https://docs.typesafe.ai/changelog.md | P | Jev 1.14 release date |
| https://docs.typesafe.ai/images.md | P | Jev image limits, header, preparation, billing |
| https://docs.typesafe.ai/primitives/box.md | P | Box output, no threshold, always a box |
| https://docs.typesafe.ai/cookbooks/reading_scanned_documents.md | P | Field reading, unreadable option, split requests |
| https://docs.typesafe.ai/cookbooks/ocr_confidence_bounding_boxes.md | P | Page plus crop check, 0.25 flag, 120 s timeout |
| https://docs.typesafe.ai/patterns/companion-noul.md | P | Choice plus companion Noul routing |
| https://docs.typesafe.ai/primitives/choice.md | P | Up to 255 options |
