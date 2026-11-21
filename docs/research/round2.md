# Ground the demo in Pakistan's real rails

The team should spend about **14 build hours** on six things, in this order. First, a Pillow generator for four watermarked mock documents (about 4 h). Second, a Raast-style "title fetch" mock with our own CoP verdict layered on top (about 2 h). Third, pre-generated Urdu audio for about 60 clips (about 2 h). Fourth, Urdu RTL and font polish (about 2 h). Fifth, a post-scam "report it" card that shows only confirmed official channels (about 1 h). Sixth, Railway Hobby in Singapore plus Cloudflare Pages, with a laptop and Cloudflare Quick Tunnel as fallback (about 2 h, deployed at least 24 h before the Sunday 18:00 PKT deadline). One more hour goes on a consent screen that cites Pakistani law and drafts accurately. The most important legal finding is that **Pakistan has no enacted data protection act as of November 2026**: the PDP Bill is still the May 2023 draft ([MoITT](https://moitt.gov.pk/Legislations); [Dawn, 7 Aug 2026](https://www.dawn.com/news/2021159)). The pitch must therefore say "built to the draft", never "compliant with the Act". The most useful payments finding is that Raast already has a "title fetch" step, which returns the account holder's name and type, and phone-alias lookups show only a masked name ([Raast System Rules Nov 2021, Scribd copy, secondary](https://www.scribd.com/document/652625569/Raast-System-Rules-Nov-2021)). Our MATCH / CLOSE_MATCH / NO_MATCH verdict is therefore an honest extension of a real Pakistani step, not an import from abroad. Round 2 also settles the cybercrime helpline: **1799 (NCCIA)**, not 1991 (FIA legacy) ([NCCIA](https://www.nccia.gov.pk/)). It also finds four places where the team docs should change. These are listed in the table below.

## One-page plan, ranked by hours

| # | Build/do | Hours | Why it matters to judges |
|---|---|---|---|
| 1 | `scripts/make_mock_docs.py`: CNIC front/back, FRC, death certificate, nikah nama, each with a banner, a diagonal SPECIMEN/MOCK watermark, MOCK in PNG metadata and a MOCK QR. Export 3 variants each (original, WhatsApp-recompressed, screenshot) plus a stamp-tamper variant | 4 | OCR, ELA and copy-move demos need inputs that look realistic but are visibly fake |
| 2 | `POST /mock/raast/title-fetch` returning title, masked title, account type, SINGLE/JOINT holding and our CoP verdict. Wire it to SafeSwitch and use fault injection for TIMEOUT | 2 | Lets judges break it live ("joint account", "timeout") and watch it route to ASK_PROOF or UNSURE |
| 3 | Azure F0 batch script that writes ~60 MP3 clips with `ur-PK-UzmaNeural`; one native speaker listens to all of them | 2 | Voice on every screen, works offline |
| 4 | RTL and fonts: `dir="rtl" lang="ur"`, logical CSS, LTR islands for CNIC and phone, a lazy Urdu font subset, Western digits | 2 | Low-literacy UX without breaking the 170 KB shell |
| 5 | Deploy Railway Hobby (Singapore) for API, Postgres and Redis, plus Cloudflare Pages for the PWA. Rehearse the Quick Tunnel fallback and record a backup video | 2 | No cold start during judging, about $5 total |
| 6 | Consent screen: 5 principles, each labelled LAW / BILL / DRAFT | 1 | Legally accurate claims that a judge can check |
| 7 | "Report this scam" card after a LIKELY_SCAM verdict (NCCIA 1799, PTA CMS, Sunwai, BISP) | 1 | Ends the scam flow with a real action |

### Where Round 2 changes the team docs

| Doc / line | Current text | Round 2 finding | Action |
|---|---|---|---|
| `CLAUDE.md` hard rule 1 / notes | Mock CNICs start with `90000` | The note proposes `99999-`. Both fall outside the real first digits 1-8 ([Wikipedia](https://en.wikipedia.org/wiki/CNIC_(Pakistan))) | **Keep `90000`** (the repo rule wins) and render the images with `90000-`. Do not mix the two prefixes |
| `03-ARCHITECTURE.md` Stack: Hosting | "Vercel (PWA)" | Vercel Hobby is "restricted to non-commercial personal use only" ([Vercel](https://vercel.com/docs/plans/hobby)). Cloudflare Pages has no bandwidth cap ([CF limits](https://developers.cloudflare.com/pages/platform/limits/)) | Optional switch to Cloudflare Pages. Vercel still probably works for a hackathon |
| `03-ARCHITECTURE.md` Stack: Speech | "Whisper or Google `ur-PK`" STT | No Google ur-PK STT was confirmed. Azure STT lists only `ur-IN` ([Azure](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=stt)) | Change to "Chrome Web Speech `ur-PK` (untested) → Azure `ur-IN` → Whisper" |
| `03-ARCHITECTURE.md` Offline: "small audio clips (Opus)" | Opus | The note recommends MP3 32 kbps, because Opus support is weaker on iOS Safari (inference, not tested) | Use MP3 (~4 KB/s). Each clip is then ~15-20 KB, which still fits the "~15 KB" budget only for clips of about 4 s or less |
| SafeSwitch 48 h / 4-day hold | UK/US-derived | No Pakistani cooling-off rule was found. The real Pakistani controls are procedural (DCS non-joint account, DDO attestation, twice-yearly certificates) ([PMAD DCS SOP](https://pmad.gov.pk/op/downloads/rev_dcs_sop.pdf)) | Keep the hold, but tell judges it is our own design. Add the `JOINT → ASK_PROOF` rule |
| Mock services table: `GET /accounts/{iban}/title` "returns the account holder's CNIC" | Returns the CNIC | Real Raast title fetch returns a name and account type, not a CNIC ([Raast Rules, secondary](https://www.scribd.com/document/652625569/Raast-System-Rules-Nov-2021)) | The mock should return `cnic_match: bool`, labelled simulated, and should not expose a CNIC |

## 1. Four mock documents follow real field order but fake every security feature

The field lists are well sourced. **Pixel positions are not**: no text source publishes CNIC, FRC, death certificate or nikah nama layouts. Every coordinate below is **our own design**. The CNIC front carries the name (English and Urdu), father's or husband's name, gender (M/F/X), country of stay, the 13-digit number, DOB, issue and expiry dates ("Lifetime" above 60), photo and signature. The back carries present and permanent addresses, a QR code and the card serial ([Wikipedia: CNIC](https://en.wikipedia.org/wiki/CNIC_(Pakistan)); [IRB Canada RIR](https://www.irb-cisr.gc.ca/en/country-information/rir/Pages/index.aspx?doc=457692)). NADRA lists "Smart CNIC" and "CNIC with QR-code" types ([NADRA](https://www.nadra.gov.pk/identityDocument/cnic)). The DOB print format conflicts between sources: they say DDMMYY ([Wikipedia](https://en.wikipedia.org/wiki/CNIC_(Pakistan))), while `DD.MM.YYYY` on printed cards is **UNVERIFIED**. Render `DD.MM.YYYY` and let the parser accept `.`, `/` and `-` with 2- or 4-digit years. The **FRC by Marriage** lists the spouse and children, can include deceased members and shows multiple marriages ([NADRA FRC](https://www.nadra.gov.pk/identityDocument/certificates/frc?tab=frc)). Its exact columns are **UNVERIFIED** (NADRA's specimen images were not viewed). The death certificate fields with secondary support are deceased name, date, place and cause of death, and graveyard ([birthcertificatepakistan.com, commercial](https://www.birthcertificatepakistan.com/obtain-nadra-death-certificate-from-pakistan/)). The CRMS issues death certificates ([NADRA ecosystem](https://www.nadra.gov.pk/ecosystem)). The **nikah nama Form II has 25 columns** and is filled in quadruplicate ([MFLO Rules copy](http://nasirlawsite.com/laws/muflorul.htm)). CNIC columns on current forms are **UNVERIFIED**. NADRA's site footer cites the NADRA Ordinance 2000 and PECA 2016 against unauthorised copying ([NADRA FRC](https://www.nadra.gov.pk/identityDocument/certificates/frc?tab=frc)). The images therefore must not use the NADRA logo, the national emblem, guilloche, a hologram or a "Government of Pakistan" header. Whether clearly marked specimens are lawful was **not checked** with any Pakistani legal source.

### Field tables (labels from sources; positions are OUR DESIGN; Urdu labels UNVERIFIED as card wording)

**CNIC front, 1012x638 px** (ID-1 at ~300 dpi, which is an inference)

| field | label EN / UR | fake value | box (x, y) |
|---|---|---|---|
| banner | MOCK IDENTITY CARD - DEMO | fixed | 0-1012, 0-80 |
| name | Name / نام | ZARA MOCKBIBI + Urdu line | 40-640, 110-190 |
| father_or_husband | Father/Husband Name / والد کا نام | ALI MOCKKHAN | 40-640, 200-280 |
| gender | Gender / جنس | F | 40-200, 300-350 |
| country_of_stay | Country of Stay (EN only) | Pakistan | 220-640, 300-350 |
| identity_number | Identity Number / شناختی نمبر | 90000-7654321-2 | 40-400, 380-430 |
| dob | Date of Birth / تاریخ پیدائش | 01.01.1970 | 420-640, 380-430 |
| issue / expiry | تاریخ اجراء / تاریخ تنسیخ | 01.01.2020 / 01.01.2030 | 40-640, 450-500 |
| photo | none | grey silhouette | 700-970, 110-430 |
| signature | Holder's Signature | scribble | 700-970, 450-540 |
| chip | CHIP (MOCK) | grey rectangle | 560-660, 520-600 (UNVERIFIED position) |

**CNIC back**: present address / موجودہ پتہ (40-700, 60-200); permanent address / مستقل پتہ (40-700, 220-360); QR encoding `MOCK|90000-...|NOT REAL` (760-970, 60-270); repeated number (40-400, 400-450, UNVERIFIED); small photo (800-950, 300-480, UNVERIFIED); serial `MOCK-000123` (40-400, 560-610).

**FRC (A4 1240x1754 @150 dpi; columns UNVERIFIED)**: title (y 80-160); Type `By Marriage`; applicant name and CNIC; certificate no `MOCK-FRC-0001` and issue date at top right. Table columns: Sr (x 60-120), Name (120-470), Relation (470-650: Self/Husband/Wife/Son/Daughter, wording UNVERIFIED), CNIC (650-930), DOB (930-1080), Status Alive/Deceased (1080-1180). Mock seal and QR at the bottom.

**Death certificate (A4)**: cited fields are deceased name (y 260), date of death / تاریخ وفات (460), place / جائے وفات (510), cause / وجہ وفات (560) and graveyard / قبرستان (610). Our UNVERIFIED design additions: Union Council (180), registration no `MOCK-DR-2026-0001` (top right), father/husband (310), deceased CNIC (360), gender (410), informant name + CNIC + relation (680-760), registration date (800), issue date (840), secretary signature with MOCK SEAL at bottom left. Render the seal as a separate PNG layer so the generator can make copy-move tamper variants.

**Nikah nama (widow subset of Form II)**: leaf no `MOCK-NR-07 / 23`; col 1 place; 2 groom/father/residence; 3 groom age; 4 bride/father/residence; 5 maiden/widow/divorcee; 6 bride age; 11 witnesses; 12 date of marriage; 13-15 dower `Rs 0 (MOCK)`; 23 solemniser; 24 registration date; 25 fee; signature band; registrar MOCK SEAL. Use one row per column in a 2-column bilingual table. CNIC on groom and bride is UNVERIFIED for real forms.

**Sketch (CNIC front, our design)**
```
+--------------------------------------------------------------+
| SPECIMEN / MOCK - NOT A REAL DOCUMENT          (MOCK SEAL)    |
| Name / نام  ZARA MOCKBIBI                     +-----------+   |
| Father Name  ALI MOCKKHAN                     |  PHOTO    |   |
| Gender F   Country of Stay Pakistan           +-----------+   |
| Identity Number 90000-7654321-2   DOB 01.01.1970  ~~sign~~    |
| Issue 01.01.2020   Expiry 01.01.2030   [CHIP MOCK]            |
|     \\ diagonal SPECIMEN / MOCK, red ~35% alpha, repeated \\  |
+--------------------------------------------------------------+
```

### What we should build/do
Spend 4 h on one Pillow script that takes a fixed synthetic person list and writes 4 document types × 4 variants. Use DejaVu Sans for Latin and Noto Nastaliq or Naskh for Urdu. Confirm that Pillow has `libraqm` on the build machine, because without it Urdu letters render unjoined. Keep the 13-digit regex `\b\d{5}-\d{7}-\d\b` as the OCR anchor. Resize to at most 1568 px per side for Jev. Write `MOCK` into the PNG metadata and the QR payload.

## 2. Raast already fetches titles, so our CoP layer extends a real step

The Raast System Rules (Nov 2021) s.3.8 define a **Title fetch** that returns the account title and account type (account or wallet). Participants must answer within **1 minute** (s.2.18(g)). For alias (mobile number) lookups the bank shows only "[First Name] [First Letter of Last Name] – [Bank]" ([Scribd copy, secondary, possibly outdated](https://www.scribd.com/document/652625569/Raast-System-Rules-Nov-2021)). A Raast ID is a mobile number linked to an account ([SBP Raast P2P](https://www.sbp.org.pk/our-subsidiaries/raast/raast-person-to-person)). **Raast returns a name for a human to read, not a match verdict.** Whether IBAN fetches are masked varies by bank (**unverified**). ISO 20022 message names are **unverified**, and no 1LINK spec was found. One anecdotal case shows a visible title did not stop an 84,000 PKR scam ([Reddit](https://www.reddit.com/r/karachi/comments/1rsso4h/ubl_let_me_lose_pkr_84000_to_fraud_no_protection/)). Federal pensions go through AGPR's **Direct Credit System** to the pensioner's own account, which "shall not be a joint account". Family pensioners file non-marriage certificates by 10 March and 10 September ([PMAD DCS SOP](https://pmad.gov.pk/op/downloads/rev_dcs_sop.pdf); [AGPR DCS form](https://agpr.gov.pk/SiteImage/Misc/files/dcs_form.pdf)). Under SBP BPRD CL 17/2025, banks open BISP Sahulat accounts from CNIC-validated data, activate them only by biometrics (or Verisys), and BISP pays via RAAST/IBFT ([SBP](https://www.sbp.org.pk/circulars/bprd-circular-letter-no-17-2025)). The government says all 10 million BISP beneficiaries are now paid through digital wallets ([MoIB](https://www.moib.gov.pk/News/66269)). The date of the BISP Raast pilot is unconfirmed ([BISP](https://bisp.gov.pk/NewsDetail/OWQxYjQxYTEtNGZmMS00M2RlLWJlM2YtNmY2N2EyZTNjYzcx)).

### Mock API shape (OUR DESIGN, all values simulated)
```
POST /mock/raast/title-fetch
req:  { request_id, proxy_type: IBAN|RAAST_ID, proxy_value: "PK00MOCK…" | "03XXMOCK…",
        expected_name, expected_cnic: "90000-…" }
data: { status: OK|ACCOUNT_NOT_FOUND|UNAVAILABLE|TIMEOUT,
        account_type: ACCOUNT|WALLET, account_holding: SINGLE|JOINT,
        bank_code: "MOCKBANK", masked_title: "Zainab A.",
        match_level: MATCH|CLOSE_MATCH|NO_MATCH|UNAVAILABLE,
        cnic_match: bool, reason_codes: [NAME_VARIANT, JOINT_ACCOUNT, CNIC_MISMATCH],
        latency_ms, simulated: true }
```
Routing rules (our design): **MATCH** only when the name is canonically equal, `cnic_match` is true and the account is SINGLE. A name variant or a JOINT account gives **CLOSE_MATCH**, which routes to ASK_PROOF (JOINT mirrors the DCS rule). NO_MATCH or a CNIC conflict routes to UNSURE. UNAVAILABLE or TIMEOUT routes to UNSURE and never pays. An injected latency above 60 s mirrors the 1-minute rule. Alias titles are always masked.

### What we should build/do
Spend 2 h on this endpoint and a fault switch, called before every payout and every SafeSwitch change. Tell judges: *"Raast already gives banks the account holder's name before a transfer, and masks it for phone-number lookups. Federal pensions must go to a non-joint account under AGPR's DCS, and BISP pays into NADRA-verified accounts over RAAST. The MATCH / CLOSE / NO MATCH verdict, the CNIC cross-check, the 48-hour hold and every account are simulated. They are a UK-style Confirmation-of-Payee layer we propose on top of the real title fetch."*

## 3. Only the Constitution and NADRA Ordinance bind; consent rules are drafts

**Law (in force):** Constitution Art. 14(1) protects "the dignity of man and, subject to law, the privacy of home" ([pakistani.org](https://www.pakistani.org/pakistan/constitution/part2.ch1.html)). NADRA Ordinance 2000 s.28 punishes improper disclosure by up to 5 years, and s.29 punishes database breach by up to 14 years ([NADRA PDF](https://www.nadra.gov.pk/assests/legalDocuments/nadra-ordianance-2000.pdf)). The Ordinance has no citizen consent mechanism. The PTA 2009 consumer regulations require operator confidentiality (an [unofficial copy](http://nasirlawsite.com/laws/tcpr.htm); the regulation number is unconfirmed). **Drafts:** the PDP Bill May 2023 ([MoITT](https://moitt.gov.pk/Legislations); text in the [ICNL copy](https://www.icnl.org/wp-content/uploads/Personal-Data-Protection-Bill-2023.pdf)); the cabinet-approved bill has not been passed and no NCPDP exists ([Legal 500](https://www.legal500.com/guides/chapter/pakistan-data-protection-cybersecurity/?export-pdf); [CyberSilo, Sep 2026](https://cybersilo.tech/pakistan-personal-data-protection-act)); the SBP Open Banking Regulations 2026, a public-consultation draft ([SBP](https://www.sbp.org.pk/assets/document/Open_Banking_Regulations_for_Public_Consulatation_Draft.pdf)); and the MoITT Data Governance Policy June 2026, marked "PROPOSED" and pending cabinet ([MoITT PDF](https://moitt.gov.pk/SiteImage/Policies/Data%20Governance%20Policy%20June%202026.pdf)). No October-November 2026 parliamentary movement was found. Clause numbers come from a mirror copy and may differ.

| # | One-line principle for the consent screen | Source | Status |
|---|---|---|---|
| 1 | Separate, clear consent for each purpose, never bundled | PDP Bill 2023 s.2(f), s.6(1); Policy 2026 cl. 12.2 | BILL / DRAFT POLICY |
| 2 | We take only the fields this purpose needs | PDP Bill s.5(2); Policy cl. 6.7 | BILL / DRAFT POLICY |
| 3 | Withdraw any time, and it takes effect at once | PDP Bill s.23(1); SBP OB Regs cl. 7.5 | BILL / CONSULTATION DRAFT |
| 4 | See who accessed your data, and ask to correct it | Policy cl. 12.3, 12.7; PDP Bill s.16, s.19 | DRAFT POLICY / BILL |
| 5 | Identity data must stay confidential | NADRA Ordinance 2000 s.28-29; Constitution Art. 14 | **LAW** |

### What we should build/do
Spend 1 h putting these 5 lines, with their status badges, on the consent screen and in the pitch: *"Built to Pakistan's draft PDP Bill and SBP's draft consent rules, ahead of enactment."* Our `GET /me/access-log` maps to Policy cl. 12.3. Two cheap additions: delete or anonymise data 30 days after consent is withdrawn, keeping consent and audit records (SBP draft cl. 13(ii)); and disclose that Chrome speech input sends audio to Google.

## 4. Show 1799, never 1991, after a scam verdict

NCCIA replaced the FIA Cyber Crime Wing under the PECA (Amendment) Act 2025, which says the wing "shall cease to exist" ([NA bill](https://www.na.gov.pk/uploads/documents/679255ee36f45_595.pdf)). NCCIA is active in 2026 ([Dawn, Aug 2026](https://www.dawn.com/news/2021570)). A Scribd claim that FIA regained cybercrime authority is **unverified** and conflicts with these sources ([Scribd](https://www.scribd.com/document/1050504385/Status-of-Federal-Investigation-Agency-FIA-and-N)). The old FIA page still advertises 1991 ([FIA](https://www.fia.gov.pk/ccw)).

| Show | Use for | Source | Confidence |
|---|---|---|---|
| NCCIA helpline **1799** | Cyber or financial fraud | [nccia.gov.pk](https://www.nccia.gov.pk/); [Financial Frauds](https://www.nccia.gov.pk/financial-frauds.php) | CONFIRMED |
| **complaint.nccia.gov.pk** (needs CNIC) | Formal complaint | [portal](https://complaint.nccia.gov.pk/) | CONFIRMED |
| helpdesk@nccia.gov.pk | Email complaint | [FAQs](https://www.nccia.gov.pk/faqs.php) | CONFIRMED |
| PTA **complaint.pta.gov.pk** / app, category "Reporting Fraudulent Call/SMS"; helpline 0800-55055 | Block a fraud number | [PTA](https://pta.gov.pk/category/consumer-complaints); [CMS](https://complaint.pta.gov.pk/UserLogIn.aspx) | CONFIRMED |
| PTA **9000** spam, **420** obnoxious, 3627 DNCR | Quick secondary option | [PTA page (2023-06-01)](https://www.pta.gov.pk/category/pta-short-codes-obnoxious-com-420-unsolicit-comdncr-3627-and-spam-reporting-9000-568848153-2023-06-01); [PTA on X](https://x.com/PTAofficialpk/status/1666354310643585027) | CONFIRMED as of 2023, not rechecked for 2026. Label "per PTA, 2023" |
| SBP **Sunwai** sunwai.sbp.org.pk | Escalate a bank complaint (bank first, then Banking Mohtasib, then SBP) | [Sunwai](https://sunwai.sbp.org.pk/about-us.html) | CONFIRMED |
| BISP **0800-26477**; only official SMS sender **8171** | BISP fee or deduction fraud | [BISP](https://bisp.gov.pk/NewsDetail/M2MzZDg0ZjctYjBkMS00YzQ1LTkwMjQtMmVhZWFiZDgyZmI0); [Contacts PDF](https://www.bisp.gov.pk/SiteImage/Misc/files/Contacts.pdf) | CONFIRMED (8171 can be spoofed, so it is evidence, not proof) |
| Your bank's number on the card or in the official app | Freeze the account if an OTP was shared | none | UNCONFIRMED (general practice) |
| 8557 | none | none | UNCONFIRMED: do not show |
| 9915 | Punjab Safe City e-challans, not PTA | survivor-pension.md | do not show as a report route |

This **resolves** survivor-pension.md §2.1's open "420 vs 9915" question: 420 is PTA's code for obnoxious messages, 9000 is PTA's spam code, and 9915 belongs to PSCA.

### What we should build/do
Spend 1 h on a card with icons and audio: "Call 1799", "Report the number to PTA", "Call your bank now if you shared a code". Show the BISP line only when the message mentions BISP. Each row carries its confidence label and source link. The architecture rule still holds: real numbers are shown only as real-world help, and the app's own mock senders stay mock.

## 5. Low-literacy Urdu: lazy Nastaliq subset, MP3 clips, and STT that only pre-fills

**Fonts.** Noto Nastaliq Urdu is on Google Fonts ([specimen](https://fonts.google.com/noto/specimen/Noto+Nastaliq+Urdu)). Its maintainers say Nastaliq lines "can grow to have a potentially unbounded line height". Clipping comes from renderers, and missing glyphs came from subsetting ([google/fonts #7810](https://github.com/google/fonts/issues/7810)). Self-hosted woff2 subsets can be generated with [google-webfonts-helper](https://gwfh.mranftl.com/fonts/noto-nastaliq-urdu?subsets=latin). Use `font-display` and preload ([web.dev](https://web.dev/learn/performance/optimize-web-fonts)). The full font sizes are **UNVERIFIED** (Nastaliq is believed to be several hundred KB), as is the default Android Urdu font. So: use the stack `"Noto Nastaliq Urdu", "Noto Naskh Arabic", system-ui`; build a woff2 subset of only the glyphs in the ~60 fixed strings; load it after first paint so it stays outside the 170 KB shell; and measure the result. Body text 20-22 px, line-height 2.0-2.2 for Nastaliq and 1.6-1.8 for Naskh (inference). Never put Urdu inside fixed-height or `overflow:hidden` boxes. Test on a cheap Android phone.

**RTL in React.** Put `dir="rtl"` on `<html>` and use `dir="auto"` for inserted text ([W3C](https://www.w3.org/International/questions/qa-html-dir.en.html)). Forward points left in RTL ([Material 2](https://m2.material.io/design/usability/bidirectionality.html)). Media controls stay LTR, a rule stated for Hebrew and not verified for Urdu ([Material 3](https://m3.material.io/foundations/layout/bidirectionality-rtl)). Mirror arrows, steppers and chevrons. Do not mirror play, phone, camera, mic, tick or money icons. Use `margin-inline-*` and `text-align: start`. Wrap CNIC and phone in `dir="ltr"` spans or inputs with `inputMode="numeric"`.

**Numerals.** No study was found. Use Western 0-9 and force them with `ur-PK-u-nu-latn` in `Intl.NumberFormat`. The claim that CNICs, banknotes and phone keypads use Western digits is **UNVERIFIED**. Write amounts as "Rs" or روپیہ ([Wise](https://wise.com/gb/currency-converter/currencies/pkr-pakistani-rupee)) next to a banknote image.

**Pictograms.** They "do not constitute a universal language". Learned conventions such as wavy lines fail, and low-literacy viewers struggle most ([Khumalo et al. 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10623492/)). Use a PKR note for money, a card shape for the CNIC, a woman with children for family, a yellow "!" triangle for warnings, and a green tick or red X (shape plus colour). Avoid thumbs-up. Always pair a pictogram with audio, and run a 5-person "what does this mean?" check if anyone is available.

**TTS: Azure pre-generation (~60 clips).** Voices: ur-PK UzmaNeural and AsadNeural ([Azure languages](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=stt)). Steps: (1) create a Speech resource on the free F0 tier, choosing a nearby region and checking ur-PK availability there (unverified per region). (2) Put the key and region in `backend/.env`, never in git. (3) A script reads the reason-code table and POSTs SSML to `/cognitiveservices/v1` with `xml:lang="ur-PK"`, voice `ur-PK-UzmaNeural`, optional `<prosody rate="-10%">` and header `X-Microsoft-OutputFormat: audio-16khz-32kbitrate-mono-mp3` ([Azure TTS REST](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech)). (4) Save `audio/<reason_code>.mp3`: about 4 KB/s and roughly 1-1.5 MB in total (an estimate), precached by the service worker outside the shell. (5) A native speaker reviews every clip and fixes pronunciation by respelling. Six thousand characters sits far below the 0.5M free tier already cited in survivor-pension.md. **Free alternatives:** MMS-TTS Urdu ([HF](https://huggingface.co/facebook/mms-tts-urd-script_arabic)) is **CC-BY-NC-4.0** ([HF](https://huggingface.co/facebook/mms-tts)), so it is acceptable for a non-commercial demo with credit, sounds robotic, and runs about 2x slower than real time on 4 CPU cores ([third-party](https://50gramx.com/inferences/mms-tts/ur/facebook-fp32-speech-hf)). edge-tts uses the same voices, but commercial use without an Azure subscription breaches Microsoft's terms ([edge-tts #261](https://github.com/rany2/edge-tts/discussions/261)) and its endpoint has broken before ([Reddit, anecdotal](https://www.reddit.com/r/ereader/comments/1muuxtr/tts_server_edge_azure_voices_stopped_working/)), so avoid it. Coqui and Piper Urdu voices are **UNVERIFIED**.

**STT.** Browser Web Speech works in Chrome, Edge and Chrome Android but not Firefox Android ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)). Whether it accepts `ur-PK` is **untested**, and it sends audio to Google. Azure STT offers `ur-IN` only. `kingabzpro/whisper-large-v3-urdu` reports **26.0% WER** on Common Voice 17 (self-reported) ([HF](https://huggingface.co/kingabzpro/whisper-large-v3-urdu)). In a COLING 2025 Urdu benchmark, Whisper came out ahead of MMS and Seamless ([ACL](https://aclanthology.org/2025.coling-main.397.pdf)). At about one wrong word in four, STT may only pre-fill fields that the user confirms by tapping.

### What we should build/do
Spend 2 h on audio (script plus review) and 2 h on RTL and fonts. Spend 15 minutes testing Chrome Android with `lang="ur-PK"` first. If it fails, fall back to Azure `ur-IN` on the backend. Add the Google audio disclosure to consent.

## 6. Railway Hobby plus Cloudflare Pages costs about $5 for the demo window

Railway's trial gives a one-time $5 credit with no card, but "when the trial ends or the credits run out, running deployments are stopped". Hobby includes $5 of usage per month ([Railway pricing](https://railway.com/pricing)). Hobby allows up to 48 GB RAM and 100 GB images per service, against the trial's 1 GB RAM and 4 GB images ([Railway plans](https://docs.railway.com/pricing/plans)). Railway has a Singapore region ([regions](https://docs.railway.com/deployments/regions)). Rates of about $10/GB-RAM-month come from a third-party source and were not checked on Railway's own page ([livemy.app](https://livemy.app/blog/railway-pricing)). By that rate, 3 days at ~1.5 GB is about $1.50, so the bill stays inside the $5 (an estimate). Render free sleeps after 15 min idle ([Render](https://render.com/docs/free)) and wakes in about 1 minute ([Render article](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)), which rules it out. Fly offers a $1 / 7-day trial with no card ([Fly](https://docs.fly.io/about/free-trial)) and 1 GB in Singapore for $8.50/month billed per second ([Fly pricing](https://docs.fly.io/about/pricing)). Koyeb free scales to zero ([Koyeb](https://www.koyeb.com/pricing)). Neon free suspends when idle ([Neon](https://neon.com/pricing)). Supabase free pauses after 1 week ([Supabase](https://supabase.com/pricing)). Upstash free allows 500K commands/month ([Upstash](https://upstash.com/pricing/redis)), which arq polling could exhaust in 1-2 days (estimate), so keep Redis on Railway. The fallback is Cloudflare Quick Tunnel (`cloudflared tunnel --url http://localhost:8080`), which needs no account or domain. Cloudflare says it is not for production, and its URL is random ([CF docs](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)). The image size of ~0.5-0.7 GB with Tesseract and OpenCV is an unsourced guess, and latency from Pakistan to Singapore was not measured.

### What we should build/do
Spend 2 h. Pay for Railway Hobby ($5) in Singapore and run API, Postgres and Redis there. Host the PWA on Cloudflare Pages (or keep Vercel), with the API URL set from an env var and CORS pinned to that origin. Bake the Tesseract `urd` traineddata into the image. Deploy by Saturday night, which is at least 24 h before the Sunday 18:00 PKT deadline, and add an uptime ping. Fallback: seeded `docker compose up` on a laptop, a Quick Tunnel started on demo morning with the PWA config updated to its URL, and a recorded backup video.

## Conclusion

Round 2 turns three things the team had treated as imported from abroad into things that are local. Payee verification extends Raast's real title fetch. The no-joint-account rule is AGPR's own. Scam reporting ends at a live Pakistani agency. The same evidence also sets hard limits on what the team may claim: no Pakistani data law beyond the Constitution and the NADRA Ordinance, no Pakistani payout-change hold, no published document layouts, and no confirmed Urdu STT. The strongest stance for judging is to label each feature as real rail, draft rule or our own design, and the tables above already do that labelling.

## Sources

| URL | Supports | Type |
|---|---|---|
| https://en.wikipedia.org/wiki/CNIC_(Pakistan) | CNIC fields, number format, Smart NIC, DOB format | secondary |
| https://www.irb-cisr.gc.ca/en/country-information/rir/Pages/index.aspx?doc=457692 | NIC data list | secondary |
| https://www.nadra.gov.pk/identityDocument/cnic | CNIC card types | primary |
| https://www.nadra.gov.pk/identityDocument/certificates/frc?tab=frc | FRC types, deceased members, copying warning | primary |
| https://www.nadra.gov.pk/ecosystem | CRMS certificates | primary |
| https://www.birthcertificatepakistan.com/obtain-nadra-death-certificate-from-pakistan/ | Death certificate fields | secondary (commercial) |
| http://nasirlawsite.com/laws/muflorul.htm | Nikah nama Form II columns | secondary (unofficial copy) |
| https://www.scribd.com/document/652625569/Raast-System-Rules-Nov-2021 | Title fetch, 1-min rule, masking | secondary copy of a primary text |
| https://www.sbp.org.pk/our-subsidiaries/raast/raast-person-to-person | Raast ID | primary |
| https://www.reddit.com/r/karachi/comments/1rsso4h/ubl_let_me_lose_pkr_84000_to_fraud_no_protection/ | Title did not prevent scam | anecdotal |
| https://pmad.gov.pk/op/downloads/rev_dcs_sop.pdf | DCS non-joint account, certificates, controls | primary |
| https://agpr.gov.pk/SiteImage/Misc/files/dcs_form.pdf | DCS form | primary |
| https://www.sbp.org.pk/circulars/bprd-circular-letter-no-17-2025 | BISP Sahulat accounts, RAAST | primary |
| https://www.moib.gov.pk/News/66269 | BISP digital wallets | primary |
| https://bisp.gov.pk/NewsDetail/OWQxYjQxYTEtNGZmMS00M2RlLWJlM2YtNmY2N2EyZTNjYzcx | BISP Raast pilot | primary |
| https://moitt.gov.pk/Legislations | PDP Bill still draft | primary |
| https://www.dawn.com/news/2021159 | Bill unpassed, Aug 2026 | secondary |
| https://www.legal500.com/guides/chapter/pakistan-data-protection-cybersecurity/?export-pdf | Cabinet approval, no NCPDP | secondary |
| https://cybersilo.tech/pakistan-personal-data-protection-act | No act as of Sep 2026 | secondary |
| https://www.icnl.org/wp-content/uploads/Personal-Data-Protection-Bill-2023.pdf | PDP Bill clauses | secondary mirror of a draft |
| https://moitt.gov.pk/SiteImage/Policies/Data%20Governance%20Policy%20June%202026.pdf | Draft policy cl. 6.7, 12.2, 12.3, 12.7 | primary (draft) |
| https://www.sbp.org.pk/assets/document/Open_Banking_Regulations_for_Public_Consulatation_Draft.pdf | Consent dashboard, revoke, 30-day delete | primary (draft) |
| https://www.nadra.gov.pk/assests/legalDocuments/nadra-ordianance-2000.pdf | s.28-29 | primary (law) |
| https://www.pakistani.org/pakistan/constitution/part2.ch1.html | Art. 14 | secondary copy of law |
| http://nasirlawsite.com/laws/tcpr.htm | PTA 2009 confidentiality | secondary (unofficial) |
| https://www.nccia.gov.pk/ | 1799, portal | primary |
| https://www.nccia.gov.pk/financial-frauds.php | Fraud contacts | primary |
| https://www.nccia.gov.pk/faqs.php | Email, routes | primary |
| https://complaint.nccia.gov.pk/ | Live portal | primary |
| https://www.na.gov.pk/uploads/documents/679255ee36f45_595.pdf | FIA CCW ceases | primary |
| https://www.dawn.com/news/2021570 | NCCIA active 2026 | secondary |
| https://www.scribd.com/document/1050504385/Status-of-Federal-Investigation-Agency-FIA-and-N | FIA regained claim (unverified) | secondary |
| https://www.fia.gov.pk/ccw | Legacy 1991 | primary (outdated) |
| https://pta.gov.pk/category/consumer-complaints | PTA fraud category | primary |
| https://complaint.pta.gov.pk/UserLogIn.aspx | CMS, 0800-55055 | primary |
| https://www.pta.gov.pk/category/pta-short-codes-obnoxious-com-420-unsolicit-comdncr-3627-and-spam-reporting-9000-568848153-2023-06-01 | 420 / 3627 / 9000 | primary (2023) |
| https://x.com/PTAofficialpk/status/1666354310643585027 | 9000 usage | primary (official account) |
| https://sunwai.sbp.org.pk/about-us.html | Sunwai escalation | primary |
| https://bisp.gov.pk/NewsDetail/M2MzZDg0ZjctYjBkMS00YzQ1LTkwMjQtMmVhZWFiZDgyZmI0 | 8171, 0800-26477 | primary |
| https://www.bisp.gov.pk/SiteImage/Misc/files/Contacts.pdf | BISP call centre | primary |
| https://fonts.google.com/noto/specimen/Noto+Nastaliq+Urdu | Font availability | primary |
| https://github.com/google/fonts/issues/7810 | Nastaliq line height and subsetting | primary (maintainers) |
| https://gwfh.mranftl.com/fonts/noto-nastaliq-urdu?subsets=latin | woff2 subsets | secondary tool |
| https://web.dev/learn/performance/optimize-web-fonts | Font loading | primary guidance |
| https://www.w3.org/International/questions/qa-html-dir.en.html | dir attribute | primary |
| https://m2.material.io/design/usability/bidirectionality.html | Icon mirroring | primary guidance |
| https://m3.material.io/foundations/layout/bidirectionality-rtl | Media controls stay LTR | primary guidance |
| https://wise.com/gb/currency-converter/currencies/pkr-pakistani-rupee | Rs / روپیہ | secondary |
| https://pmc.ncbi.nlm.nih.gov/articles/PMC10623492/ | Pictogram comprehension limits | primary research |
| https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=stt | ur-PK voices, ur-IN STT only | primary |
| https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech | REST call, output formats | primary |
| https://huggingface.co/facebook/mms-tts-urd-script_arabic | MMS Urdu TTS | primary |
| https://huggingface.co/facebook/mms-tts | CC-BY-NC-4.0 licence | primary |
| https://50gramx.com/inferences/mms-tts/ur/facebook-fp32-speech-hf | MMS speed | secondary |
| https://github.com/rany2/edge-tts/discussions/261 | edge-tts terms risk | secondary |
| https://www.reddit.com/r/ereader/comments/1muuxtr/tts_server_edge_azure_voices_stopped_working/ | Edge endpoint breakage | anecdotal |
| https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API | SpeechRecognition support | primary docs |
| https://huggingface.co/kingabzpro/whisper-large-v3-urdu | 26.0% WER (self-reported) | secondary |
| https://aclanthology.org/2025.coling-main.397.pdf | Whisper best on Urdu | primary research |
| https://railway.com/pricing | Trial, Hobby $5, stop on credit end | primary |
| https://docs.railway.com/pricing/plans | Per-service limits | primary |
| https://docs.railway.com/deployments/regions | Singapore region | primary |
| https://livemy.app/blog/railway-pricing | Usage rates | secondary |
| https://render.com/docs/free | Sleep, 30-day Postgres | primary |
| https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026 | ~1 min wake | primary |
| https://docs.fly.io/about/pricing | Fly prices by region | primary |
| https://docs.fly.io/about/free-trial | $1 / 7-day trial, no card | primary |
| https://www.koyeb.com/pricing | Scale to zero | primary |
| https://neon.com/pricing | Autosuspend | primary |
| https://supabase.com/pricing | 1-week pause | primary |
| https://upstash.com/pricing/redis | 500K commands | primary |
| https://developers.cloudflare.com/pages/platform/limits/ | Pages limits | primary |
| https://vercel.com/docs/plans/hobby | Non-commercial only | primary |
| https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/ | Quick Tunnel fallback | primary |
