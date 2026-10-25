(ns kotoba.examlaw
  "**What a tax authority must have done before it may examine — by jurisdiction.**

  Sibling of `kotoba-lang/taxlaw` and `kotoba-lang/worklaw`, and deliberately
  the same shape, with one inversion that is the reason this library is
  separate rather than a namespace inside `taxlaw`.

  `taxlaw` and `worklaw` are keyed on a *private party's* obligation, so their
  conservative direction is to withhold a pass: absence is never sufficiency.
  This library is keyed on a *state power*. The conservative direction
  therefore flips:

      ABSENCE IS NEVER AUTHORITY.

  An uncatalogued jurisdiction does not return `:permitted`. It returns
  `:no-catalog`, and `authorized?` is false. A caller cannot read *we have
  not read this country's procedure code* as *the official may proceed*.

  This library never exercises, simulates exercising, or proposes exercising
  any examination power. It answers what a named statute requires and reports
  which of those requirements the supplied record does not establish. Every
  condition that the statute commits to an official's own finding is returned
  as `:official-determination` and is never machine-satisfiable — see
  `disposition`.")

;; ---------------------------------------------------------------------------
;; Sources — every quote below was fetched from the official publisher and is
;; a byte-exact span of the text that endpoint returned on the date recorded.
;; ---------------------------------------------------------------------------

(def sources
  "source-id -> the instrument, the article, and the span actually read.

  `:source/quote` is verbatim. Where a span is elided the elision is marked
  with `…` and `:source/elided?` is true, so a test can assert that no
  unmarked quote was shortened."
  {:jp-kokuzei-74-2-1
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の二第一項"
    :source/heading "（当該職員の所得税等に関する調査に係る質問検査権）"
    :source/quote "所得税、法人税、地方法人税又は消費税に関する調査について必要があるときは、次の各号に掲げる調査の区分に応じ、当該各号に定める者に質問し、その者の事業に関する帳簿書類その他の物件…を検査し、又は当該物件…の提示若しくは提出を求めることができる。"
    :source/elided? true
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-74-7
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の七"
    :source/heading "（提出物件の留置き）"
    :source/quote "国税庁等又は税関の当該職員は、国税の調査について必要があるときは、当該調査において提出された物件を留め置くことができる。"
    :source/elided? false
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-74-8
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の八"
    :source/heading "（権限の解釈）"
    :source/quote "第七十四条の二から第七十四条の七まで（当該職員の質問検査権等）又は前条の規定による当該職員又は国税局長の権限は、犯罪捜査のために認められたものと解してはならない。"
    :source/elided? false
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-74-9-1
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の九第一項"
    :source/heading "（納税義務者に対する調査の事前通知等）"
    :source/quote "…納税義務者に対し実地の調査…において第七十四条の二から第七十四条の六まで（当該職員の質問検査権）の規定による質問、検査又は提示若しくは提出の要求（以下「質問検査等」という。）を行わせる場合には、あらかじめ、当該納税義務者（当該納税義務者について税務代理人がある場合には、当該税務代理人を含む。）に対し、その旨及び次に掲げる事項を通知するものとする。"
    :source/elided? true
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-74-9-4
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の九第四項"
    :source/heading "（納税義務者に対する調査の事前通知等）"
    :source/quote "第一項の規定は、当該職員が、当該調査により当該調査に係る同項第三号から第六号までに掲げる事項以外の事項について非違が疑われることとなつた場合において、当該事項に関し質問検査等を行うことを妨げるものではない。この場合において、同項の規定は、当該事項に関する質問検査等については、適用しない。"
    :source/elided? false
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-74-10
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の十"
    :source/heading "（事前通知を要しない場合）"
    :source/quote "前条第一項の規定にかかわらず、税務署長等が調査の相手方である同条第三項第一号に掲げる納税義務者の申告若しくは過去の調査結果の内容又はその営む事業内容に関する情報その他国税庁等若しくは税関が保有する情報に鑑み、違法又は不当な行為を容易にし、正確な課税標準等又は税額等の把握を困難にするおそれその他国税に関する調査の適正な遂行に支障を及ぼすおそれがあると認める場合には、同条第一項の規定による通知を要しない。"
    :source/elided? false
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-74-11-1
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の十一第一項"
    :source/heading "（調査の終了の際の手続）"
    :source/quote "税務署長等は、国税に関する実地の調査を行つた結果、更正決定等…をすべきと認められない場合には、納税義務者…であつて当該調査において質問検査等の相手方となつた者に対し、その時点において更正決定等をすべきと認められない旨を書面により通知するものとする。"
    :source/elided? true
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-74-11-2
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の十一第二項"
    :source/heading "（調査の終了の際の手続）"
    :source/quote "国税に関する調査の結果、更正決定等をすべきと認める場合には、当該職員は、当該納税義務者に対し、その調査結果の内容（更正決定等をすべきと認めた額及びその理由を含む。）を説明するものとする。"
    :source/elided? false
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-74-11-3
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の十一第三項"
    :source/heading "（調査の終了の際の手続）"
    :source/quote "前項の規定による説明をする場合において、当該職員は、当該納税義務者に対し修正申告又は期限後申告を勧奨することができる。この場合において、当該調査の結果に関し当該納税義務者が納税申告書を提出した場合には不服申立てをすることはできないが更正の請求をすることはできる旨を説明するとともに、その旨を記載した書面を交付しなければならない。"
    :source/elided? false
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-74-11-5
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の十一第五項"
    :source/heading "（調査の終了の際の手続）"
    :source/quote "第一項の通知をした後又は第二項の調査（実地の調査に限る。）の結果につき納税義務者から修正申告書若しくは期限後申告書の提出若しくは源泉徴収等による国税の納付があつた後若しくは更正決定等をした後においても、当該職員は、新たに得られた情報に照らし非違があると認めるときは、第七十四条の二から第七十四条の六まで（当該職員の質問検査権）の規定に基づき、…質問検査等を行うことができる。"
    :source/elided? true
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-74-13
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第七十四条の十三"
    :source/heading "（身分証明書の携帯等）"
    :source/quote "国税庁等又は税関の当該職員は、第七十四条の二から第七十四条の六まで（当該職員の質問検査権）の規定による質問、検査、提示若しくは提出の要求、閲覧の要求、採取、移動の禁止若しくは封かんの実施をする場合又は前条の職務を執行する場合には、その身分を示す証明書を携帯し、関係人の請求があつたときは、これを提示しなければならない。"
    :source/elided? false
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :jp-kokuzei-128
   {:source/jurisdiction [:jp]
    :source/law-id "337AC0000000066"
    :source/title "国税通則法"
    :source/article "第百二十八条第二号"
    :source/heading ""
    :source/quote "第七十四条の二、第七十四条の三（第二項を除く。）若しくは第七十四条の四から第七十四条の六まで（当該職員の質問検査権）の規定による当該職員の質問に対して答弁せず、若しくは偽りの答弁をし、又はこれらの規定による検査、採取、移動の禁止若しくは封かんの実施を拒み、妨げ、若しくは忌避した者"
    :source/elided? false
    :source/revision "337AC0000000066_20260624_508AC0000000046"
    :source/publisher :e-gov
    :source/url "https://laws.e-gov.go.jp/api/2/law_data/337AC0000000066"
    :source/fetched "2026-08-22"}

   :us-irc-7602-a
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7602(a)"
    :source/title "Internal Revenue Code"
    :source/article "§7602(a)"
    :source/heading "Examination of books and witnesses — Authority to summon, etc."
    :source/quote "For the purpose of ascertaining the correctness of any return, making a return where none has been made, determining the liability of any person for any internal revenue tax…, or collecting any such liability, the Secretary is authorized— (1) To examine any books, papers, records, or other data which may be relevant or material to such inquiry;"
    :source/elided? true
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap78-subchapA-sec7602.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7602-b
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7602(b)"
    :source/title "Internal Revenue Code"
    :source/article "§7602(b)"
    :source/heading "Purpose may include inquiry into offense"
    :source/quote "The purposes for which the Secretary may take any action described in paragraph (1), (2), or (3) of subsection (a) include the purpose of inquiring into any offense connected with the administration or enforcement of the internal revenue laws."
    :source/elided? false
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap78-subchapA-sec7602.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7602-c
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7602(c)(1)"
    :source/title "Internal Revenue Code"
    :source/article "§7602(c)(1)"
    :source/heading "Notice of contact of third parties — General notice"
    :source/quote "An officer or employee of the Internal Revenue Service may not contact any person other than the taxpayer with respect to the determination or collection of the tax liability of such taxpayer unless such contact occurs during a period (not greater than 1 year) which is specified in a notice which— (A) informs the taxpayer that contacts with persons other than the taxpayer are intended to be made during such period, and (B) except as otherwise provided by the Secretary, is provided to the taxpayer not later than 45 days before the beginning of such period."
    :source/elided? false
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap78-subchapA-sec7602.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7602-c-1-intent
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7602(c)(1)"
    :source/title "Internal Revenue Code"
    :source/article "§7602(c)(1), flush text"
    :source/heading "Notice of contact of third parties — General notice"
    :source/quote "A notice shall not be issued under this paragraph unless there is an intent at the time such notice is issued to contact persons other than the taxpayer during the period specified in such notice."
    :source/elided? false
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap78-subchapA-sec7602.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7602-c-3
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7602(c)(3)"
    :source/title "Internal Revenue Code"
    :source/article "§7602(c)(3)"
    :source/heading "Notice of contact of third parties — Exceptions"
    :source/quote "This subsection shall not apply— (A) to any contact which the taxpayer has authorized; (B) if the Secretary determines for good cause shown that such notice would jeopardize collection of any tax or such notice may involve reprisal against any person; or (C) with respect to any pending criminal investigation."
    :source/elided? false
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap78-subchapA-sec7602.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7602-d
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7602(d)(1)"
    :source/title "Internal Revenue Code"
    :source/article "§7602(d)(1)"
    :source/heading "No administrative summons when there is Justice Department referral"
    :source/quote "No summons may be issued under this title, and the Secretary may not begin any action under section 7604 to enforce any summons, with respect to any person if a Justice Department referral is in effect with respect to such person."
    :source/elided? false
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap78-subchapA-sec7602.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7605-a
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7605(a)"
    :source/title "Internal Revenue Code"
    :source/article "§7605(a)"
    :source/heading "Time and place of examination — Time and place"
    :source/quote "The time and place of examination pursuant to the provisions of section 6420(e)(2), 6421(g)(2), 6427(j)(2), or 7602 shall be such time and place as may be fixed by the Secretary and as are reasonable under the circumstances. In the case of a summons under authority of paragraph (2) of section 7602…, the date fixed for appearance before the Secretary shall not be less than 10 days from the date of the summons."
    :source/elided? true
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap78-subchapA-sec7605.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7605-b
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7605(b)"
    :source/title "Internal Revenue Code"
    :source/article "§7605(b)"
    :source/heading "Restrictions on examination of taxpayer"
    :source/quote "No taxpayer shall be subjected to unnecessary examination or investigations, and only one inspection of a taxpayer's books of account shall be made for each taxable year unless the taxpayer requests otherwise or unless the Secretary, after investigation, notifies the taxpayer in writing that an additional inspection is necessary."
    :source/elided? false
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap78-subchapA-sec7605.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7521-b1
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7521(b)(1)"
    :source/title "Internal Revenue Code"
    :source/article "§7521(b)(1)"
    :source/heading "Procedures involving taxpayer interviews — Explanations of processes"
    :source/quote "An officer or employee of the Internal Revenue Service shall before or at an initial interview provide to the taxpayer— (A) in the case of an in-person interview with the taxpayer relating to the determination of any tax, an explanation of the audit process and the taxpayer's rights under such process,…"
    :source/elided? true
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap77-sec7521.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7521-b2
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7521(b)(2)"
    :source/title "Internal Revenue Code"
    :source/article "§7521(b)(2)"
    :source/heading "Procedures involving taxpayer interviews — Right of consultation"
    :source/quote "If the taxpayer clearly states to an officer or employee of the Internal Revenue Service at any time during any interview (other than an interview initiated by an administrative summons issued under subchapter A of chapter 78) that the taxpayer wishes to consult with an attorney, certified public accountant, enrolled agent, enrolled actuary, or any other person permitted to represent the taxpayer before the Internal Revenue Service, such officer or employee shall suspend such interview regardless of whether the taxpayer may have answered one or more questions."
    :source/elided? false
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap77-sec7521.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7521-a1
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7521(a)(1)"
    :source/title "Internal Revenue Code"
    :source/article "§7521(a)(1)"
    :source/heading "Procedures involving taxpayer interviews — Recording by taxpayer"
    :source/quote "Any officer or employee of the Internal Revenue Service in connection with any in-person interview with any taxpayer relating to the determination or collection of any tax shall, upon advance request of such taxpayer, allow the taxpayer to make an audio recording of such interview at the taxpayer's own expense and with the taxpayer's own equipment."
    :source/elided? false
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap77-sec7521.htm"
    :source/fetched "2026-08-22"}

   :us-irc-7521-d
   {:source/jurisdiction [:us]
    :source/law-id "26 U.S.C. §7521(d)"
    :source/title "Internal Revenue Code"
    :source/article "§7521(d)"
    :source/heading "Section not to apply to certain investigations"
    :source/quote "This section shall not apply to criminal investigations or investigations relating to the integrity of any officer or employee of the Internal Revenue Service."
    :source/elided? false
    :source/revision "United States Code, 2023 Edition"
    :source/publisher :govinfo
    :source/url "https://www.govinfo.gov/content/pkg/USCODE-2023-title26/html/USCODE-2023-title26-subtitleF-chap77-sec7521.htm"
    :source/fetched "2026-08-22"}

   :eu-dac-11-1
   {:source/jurisdiction [:eu]
    :source/law-id "02011L0016-20240101"
    :source/title "Council Directive 2011/16/EU on administrative cooperation in the field of taxation"
    :source/article "Article 11(1)"
    :source/heading "Presence in administrative offices and participation in administrative enquiries — Scope and conditions"
    :source/quote "With a view to exchanging the information referred to in Article 1(1), the competent authority of a Member State may request the competent authority of another Member State that officials authorised by the former and in accordance with the procedural arrangements laid down by the latter: (a) be present in the offices where the administrative authorities of the requested Member State carry out their duties; (b) be present during administrative enquiries carried out in the territory of the requested Member State; (c) participate in the administrative enquiries carried out by the requested Member State through the use of electronic means of communication, where appropriate."
    :source/elided? false
    :source/revision "consolidated text of 2024-01-01"
    :source/publisher :eur-lex
    :source/url "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02011L0016-20240101"
    :source/fetched "2026-08-22"}

   :eu-dac-12a-2
   {:source/jurisdiction [:eu]
    :source/law-id "02011L0016-20240101"
    :source/title "Council Directive 2011/16/EU on administrative cooperation in the field of taxation"
    :source/article "Article 12a(2)"
    :source/heading "Joint audits"
    :source/quote "Joint audits shall be conducted in a pre-agreed and coordinated manner, including linguistic arrangements, by the competent authorities of the requesting and the requested Member States, and in accordance with the laws and procedural requirements of the Member State where the activities of a joint audit take place.… While complying with the laws of the Member State where the activities of the joint audit take place, officials of another Member State shall not exercise any powers that would exceed the scope of the powers granted to them under the laws of their Member State."
    :source/elided? true
    :source/revision "consolidated text of 2024-01-01"
    :source/publisher :eur-lex
    :source/url "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02011L0016-20240101"
    :source/fetched "2026-08-22"}

   :eu-dac-12a-1
   {:source/jurisdiction [:eu]
    :source/law-id "02011L0016-20240101"
    :source/title "Council Directive 2011/16/EU on administrative cooperation in the field of taxation"
    :source/article "Article 12a(1)"
    :source/heading "Joint audits"
    :source/quote "The competent authority of one or more Member States may request the competent authority of another Member State (or other Member States) to conduct a joint audit. The requested competent authorities shall respond to the request for a joint audit within 60 days of the receipt of the request. The requested competent authorities may reject a request for a joint audit by the competent authority of a Member State on justified grounds."
    :source/elided? false
    :source/revision "consolidated text of 2024-01-01"
    :source/publisher :eur-lex
    :source/url "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02011L0016-20240101"
    :source/fetched "2026-08-22"}

   :eu-dac-12-1
   {:source/jurisdiction [:eu]
    :source/law-id "02011L0016-20240101"
    :source/title "Council Directive 2011/16/EU on administrative cooperation in the field of taxation"
    :source/article "Article 12(1)"
    :source/heading "Simultaneous controls"
    :source/quote "Where two or more Member States agree to conduct simultaneous controls, in their own territory, of one or more persons of common or complementary interest to them, with a view to exchanging the information thus obtained, paragraphs 2, 3 and 4 shall apply."
    :source/elided? false
    :source/revision "consolidated text of 2024-01-01"
    :source/publisher :eur-lex
    :source/url "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02011L0016-20240101"
    :source/fetched "2026-08-22"}

   :de-ao-193-1
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 193 Abs. 1"
    :source/heading "Zulässigkeit einer Außenprüfung"
    :source/quote "Eine Außenprüfung ist zulässig bei Steuerpflichtigen, die einen gewerblichen oder land- und forstwirtschaftlichen Betrieb unterhalten, die freiberuflich tätig sind und bei Steuerpflichtigen im Sinne des § 147a."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-193-2
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 193 Abs. 2"
    :source/heading "Zulässigkeit einer Außenprüfung"
    :source/quote "Bei anderen als den in Absatz 1 bezeichneten Steuerpflichtigen ist eine Außenprüfung zulässig, 1. soweit sie die Verpflichtung dieser Steuerpflichtigen betrifft, für Rechnung eines anderen Steuern zu entrichten oder Steuern einzubehalten und abzuführen, 2. wenn die für die Besteuerung erheblichen Verhältnisse der Aufklärung bedürfen und eine Prüfung an Amtsstelle nach Art und Umfang des zu prüfenden Sachverhalts nicht zweckmäßig ist oder 3. wenn ein Steuerpflichtiger seinen Mitwirkungspflichten nach § 12 des Gesetzes zur Abwehr von Steuervermeidung und unfairem Steuerwettbewerb nicht nachkommt."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-196
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 196"
    :source/heading "Prüfungsanordnung"
    :source/quote "Die Finanzbehörde bestimmt den Umfang der Außenprüfung in einer schriftlich oder elektronisch zu erteilenden Prüfungsanordnung mit Rechtsbehelfsbelehrung nach § 356."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-197-1
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 197 Abs. 1"
    :source/heading "Bekanntgabe der Prüfungsanordnung"
    :source/quote "Die Prüfungsanordnung sowie der voraussichtliche Prüfungsbeginn und die Namen der Prüfer sind dem Steuerpflichtigen, bei dem die Außenprüfung durchgeführt werden soll, angemessene Zeit vor Beginn der Prüfung bekannt zu geben, wenn der Prüfungszweck dadurch nicht gefährdet wird. Der Steuerpflichtige kann auf die Einhaltung der Frist verzichten."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-197-2
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 197 Abs. 2"
    :source/heading "Bekanntgabe der Prüfungsanordnung"
    :source/quote "Auf Antrag der Steuerpflichtigen soll der Beginn der Außenprüfung auf einen anderen Zeitpunkt verlegt werden, wenn dafür wichtige Gründe glaubhaft gemacht werden."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-198
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 198"
    :source/heading "Ausweispflicht, Beginn der Außenprüfung"
    :source/quote "Die Prüfer haben sich bei Erscheinen unverzüglich auszuweisen. Der Beginn der Außenprüfung ist unter Angabe von Datum und Uhrzeit aktenkundig zu machen."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-199-1
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 199 Abs. 1"
    :source/heading "Prüfungsgrundsätze"
    :source/quote "Der Außenprüfer hat die tatsächlichen und rechtlichen Verhältnisse, die für die Steuerpflicht und für die Bemessung der Steuer maßgebend sind (Besteuerungsgrundlagen), zugunsten wie zuungunsten des Steuerpflichtigen zu prüfen."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-199-2
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 199 Abs. 2"
    :source/heading "Prüfungsgrundsätze"
    :source/quote "Der Steuerpflichtige ist während der Außenprüfung über die festgestellten Sachverhalte und die möglichen steuerlichen Auswirkungen zu unterrichten, wenn dadurch Zweck und Ablauf der Prüfung nicht beeinträchtigt werden."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-200-3
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 200 Abs. 3"
    :source/heading "Mitwirkungspflichten des Steuerpflichtigen"
    :source/quote "Die Außenprüfung findet während der üblichen Geschäfts- oder Arbeitszeit statt. Die Prüfer sind berechtigt, Grundstücke und Betriebsräume zu betreten und zu besichtigen. Bei der Betriebsbesichtigung soll der Betriebsinhaber oder sein Beauftragter hinzugezogen werden."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-201-1
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 201 Abs. 1"
    :source/heading "Schlussbesprechung"
    :source/quote "Über das Ergebnis der Außenprüfung ist eine Besprechung abzuhalten (Schlussbesprechung), es sei denn, dass sich nach dem Ergebnis der Außenprüfung keine Änderung der Besteuerungsgrundlagen ergibt oder dass der Steuerpflichtige auf die Besprechung verzichtet."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-201-2
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 201 Abs. 2"
    :source/heading "Schlussbesprechung"
    :source/quote "Besteht die Möglichkeit, dass auf Grund der Prüfungsfeststellungen ein Straf- oder Bußgeldverfahren durchgeführt werden muss, soll der Steuerpflichtige darauf hingewiesen werden, dass die straf- oder bußgeldrechtliche Würdigung einem besonderen Verfahren vorbehalten bleibt."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-202-1
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 202 Abs. 1"
    :source/heading "Inhalt und Bekanntgabe des Prüfungsberichts"
    :source/quote "Über das Ergebnis der Außenprüfung ergeht ein schriftlicher oder elektronischer Bericht (Prüfungsbericht).… Führt die Außenprüfung zu keiner Änderung der Besteuerungsgrundlagen, so genügt es, wenn dies dem Steuerpflichtigen schriftlich oder elektronisch mitgeteilt wird."
    :source/elided? true
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :de-ao-202-2
   {:source/jurisdiction [:eu :de]
    :source/law-id "BJNR006130976"
    :source/title "Abgabenordnung (AO)"
    :source/article "§ 202 Abs. 2"
    :source/heading "Inhalt und Bekanntgabe des Prüfungsberichts"
    :source/quote "Die Finanzbehörde hat dem Steuerpflichtigen auf Antrag den Prüfungsbericht vor seiner Auswertung zu übersenden und ihm Gelegenheit zu geben, in angemessener Zeit dazu Stellung zu nehmen."
    :source/elided? false
    :source/revision "gesetze-im-internet.de consolidated XML, retrieved 2026-08-22"
    :source/publisher :gesetze-im-internet
    :source/url "https://www.gesetze-im-internet.de/ao_1977/xml.zip"
    :source/fetched "2026-08-22"}

   :es-lgt-141
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 141"
    :source/heading "La inspección tributaria"
    :source/quote "La inspección tributaria consiste en el ejercicio de las funciones administrativas dirigidas a: a) La investigación de los supuestos de hecho de las obligaciones tributarias para el descubrimiento de los que sean ignorados por la Administración. b) La comprobación de la veracidad y exactitud de las declaraciones presentadas por los obligados tributarios.…"
    :source/elided? true
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-142-2
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 142.2"
    :source/heading "Facultades de la inspección de los tributos"
    :source/quote "Si la persona bajo cuya custodia se encontraren los lugares mencionados en el párrafo anterior se opusiera a la entrada de los funcionarios de la inspección de los tributos, se precisará la autorización escrita de la autoridad administrativa que reglamentariamente se determine. Cuando en el ejercicio de las actuaciones inspectoras sea necesario entrar en el domicilio constitucionalmente protegido del obligado tributario, se aplicará lo dispuesto en el artículo 113 de esta ley."
    :source/elided? false
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-147-2
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 147.2"
    :source/heading "Iniciación del procedimiento de inspección"
    :source/quote "Los obligados tributarios deben ser informados al inicio de las actuaciones del procedimiento de inspección sobre la naturaleza y alcance de las mismas, así como de sus derechos y obligaciones en el curso de tales actuaciones."
    :source/elided? false
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-148-3
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 148.3"
    :source/heading "Alcance de las actuaciones del procedimiento de inspección"
    :source/quote "Cuando las actuaciones del procedimiento de inspección hubieran terminado con una liquidación provisional, el objeto de las mismas no podrá regularizarse nuevamente en un procedimiento de inspección que se inicie con posterioridad salvo que concurra alguna de las circunstancias a que se refiere el párrafo a) del apartado 4 del artículo 101 de esta ley y exclusivamente en relación con los elementos de la obligación tributaria afectados por dichas circunstancias."
    :source/elided? false
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-150-1
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 150.1"
    :source/heading "Plazo de las actuaciones inspectoras"
    :source/quote "Las actuaciones del procedimiento de inspección deberán concluir en el plazo de 12 meses contado desde la fecha de notificación al obligado tributario del inicio del mismo.… No obstante, podrá ampliarse dicho plazo, con el alcance y requisitos que reglamentariamente se determinen, por otro período que no podrá exceder de 12 meses, cuando en las actuaciones concurra alguna de las siguientes circunstancias: a) Cuando revistan especial complejidad.… b) Cuando en el transcurso de las mismas se descubra que el obligado tributario ha ocultado a la Administración tributaria alguna de las actividades empresariales o profesionales que realice. Los acuerdos de ampliación del plazo legalmente previsto serán, en todo caso, motivados, con referencia a los hechos y fundamentos de derecho."
    :source/elided? true
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-151-2
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 151.2"
    :source/heading "Lugar de las actuaciones inspectoras"
    :source/quote "La inspección podrá personarse sin previa comunicación en las empresas, oficinas, dependencias, instalaciones o almacenes del obligado tributario, entendiéndose las actuaciones con éste o con el encargado o responsable de los locales."
    :source/elided? false
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-151-3
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 151.3"
    :source/heading "Lugar de las actuaciones inspectoras"
    :source/quote "Los libros y demás documentación a los que se refiere el apartado 1 del artículo 142 de esta ley deberán ser examinados en el domicilio, local, despacho u oficina del obligado tributario, en presencia del mismo o de la persona que designe, salvo que el obligado tributario consienta su examen en las oficinas públicas."
    :source/elided? false
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-152-2
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 152.2"
    :source/heading "Horario de las actuaciones inspectoras"
    :source/quote "Si las actuaciones se desarrollan en los locales del interesado se respetará la jornada laboral de oficina o de la actividad que se realice en los mismos, con la posibilidad de que pueda actuarse de común acuerdo en otras horas o días."
    :source/elided? false
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-156-1
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 156.1"
    :source/heading "Actas de conformidad"
    :source/quote "Con carácter previo a la firma del acta de conformidad se concederá trámite de audiencia al interesado para que alegue lo que convenga a su derecho."
    :source/elided? false
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-157-1
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 157.1"
    :source/heading "Actas de disconformidad"
    :source/quote "Con carácter previo a la firma del acta de disconformidad se concederá trámite de audiencia al interesado para que alegue lo que convenga a su derecho."
    :source/elided? false
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-157-2
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 157.2"
    :source/heading "Actas de disconformidad"
    :source/quote "Cuando el obligado tributario o su representante no suscriba el acta o manifieste su disconformidad con la propuesta de regularización que formule la inspección de los tributos, se hará constar expresamente esta circunstancia en el acta, a la que se acompañará un informe del actuario en el que se expongan los fundamentos de derecho en que se base la propuesta de regularización."
    :source/elided? false
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}

   :es-lgt-34-1-f
   {:source/jurisdiction [:eu :es]
    :source/law-id "BOE-A-2003-23186"
    :source/title "Ley 58/2003, de 17 de diciembre, General Tributaria"
    :source/article "Artículo 34.1.f)"
    :source/heading "Derechos y garantías de los obligados tributarios"
    :source/quote "Derecho a conocer la identidad de las autoridades y personal al servicio de la Administración tributaria bajo cuya responsabilidad se tramitan las actuaciones y procedimientos tributarios en los que tenga la condición de interesado."
    :source/elided? false
    :source/revision "texto consolidado, fecha_actualizacion 20260626132602"
    :source/publisher :boe
    :source/url "https://www.boe.es/diario_boe/xml.php?id=BOE-A-2003-23186"
    :source/fetched "2026-08-22"}})

(def catalog-verification
  "How the quotes above were obtained, so a reader can repeat it.

  `:absences` are the findings that took the most work and that a reader is
  most likely to have wrong from folklore. Each one is a search that was run
  and returned nothing, not a topic nobody looked at."
  {:verified-on "2026-08-22"
   :method "Each instrument was fetched from its official publisher's endpoint
            and the article extracted from the returned document. No quote was
            typed from memory or from a secondary source."
   :absences
   [{:absence/id :us-no-general-advance-notice
     :absence/jurisdiction [:us]
     :absence/claim "The Internal Revenue Code contains no general requirement
                     that a taxpayer be notified before an examination begins."
     :absence/searched "§7602, §7605, §7521 read in full."
     :absence/near-misses [:us-irc-7602-c :us-irc-7521-b1]
     :absence/note "§7602(c) is notice of contacting THIRD PARTIES, not notice
                    of the examination. §7521(b)(1) is an explanation given
                    'before or at an initial interview' — at is not before, and
                    an interview is not the examination. Neither is a general
                    advance-notice rule, and treating either as one would
                    manufacture a taxpayer protection that Congress did not
                    enact."}
    {:absence/id :eu-no-examination-power
     :absence/jurisdiction [:eu]
     :absence/claim "Directive 2011/16/EU confers no power on any EU body to
                     examine a taxpayer. Examination is Member State law."
     :absence/searched "Articles 11, 12, 12a of the 2024-01-01 consolidation."
     :absence/near-misses [:eu-dac-11-1 :eu-dac-12a-2]
     :absence/note "Every cooperation article routes the actual power back to a
                    Member State: Article 11(1) 'in accordance with the
                    procedural arrangements laid down by the latter', Article
                    12a(2) 'in accordance with the laws and procedural
                    requirements of the Member State where the activities of a
                    joint audit take place'."}
    {:absence/id :eu-12a-not-in-2023-consolidation
     :absence/jurisdiction [:eu]
     :absence/claim "Article 12a (joint audits) is absent from the 2023-01-01
                     consolidated text and present in the 2024-01-01 one."
     :absence/searched "Both consolidations fetched and searched for 'Article 12a'."
     :absence/near-misses []
     :absence/note "Measured, not inferred from the DAC7 application date. A
                    catalog pinned to the wrong consolidation would report that
                    joint audits do not exist."}
    {:absence/id :fr-source-not-retrievable
     :absence/jurisdiction [:eu :fr]
     :absence/claim "France is NOT catalogued, and the reason is retrieval, not
                     priority. By economic size it is the jurisdiction that
                     should have been read before Spain."
     :absence/searched "legifrance.gouv.fr/codes/article_lc/<id> returned HTTP 403
                        on 2026-08-22. The Légifrance bulk API (PISTE) needs
                        credentials this workspace does not hold."
     :absence/near-misses []
     :absence/note "Bot protection was not circumvented, and no secondary source
                    was used in its place. Every other quote in this catalog is a
                    byte-exact span from an official endpoint, and one article of
                    the Livre des procédures fiscales paraphrased from a textbook
                    would be indistinguishable in the data from the rest. The
                    honest state is :no-catalog, which is what [:eu :fr] returns.
                    Next step is a PISTE credential or the DILA LEGI open-data
                    dump, not a different reading of the same 403."}
    {:absence/id :it-source-is-a-javascript-shell
     :absence/jurisdiction [:eu :it]
     :absence/claim "Italy is NOT catalogued for the same class of reason."
     :absence/searched "normattiva.it urn:nir for DPR 600/1973 returned HTTP 200
                        and 373 KB, of which the extractable text was 9.5 KB of
                        site chrome and no article text at all."
     :absence/near-misses []
     :absence/note "A 200 that carries no law is more dangerous than a 403,
                    because a pipeline that checks status codes records it as a
                    successful fetch. This one was caught by asserting on the
                    presence of an article heading in the extracted text rather
                    than on the response code."}
    {:absence/id :jp-127-is-not-the-refusal-penalty
     :absence/jurisdiction [:jp]
     :absence/claim "国税通則法第百二十七条 is the penalty for an official who
                     leaks or misappropriates a secret learned on duty. The
                     penalty for refusing an examination is 第百二十八条第二号."
     :absence/searched "Both articles fetched in full and read."
     :absence/near-misses [:jp-kokuzei-128]
     :absence/note "127 was reached for first here, on the strength of a
                    recollection, and it was wrong. It is recorded because the
                    wrong article is the one a reader is likely to arrive with."}]})

;; ---------------------------------------------------------------------------
;; The action universe and the facet universe
;; ---------------------------------------------------------------------------

(def actions
  "The examination steps this library can be asked about.

  A jurisdiction that does not list an action does not thereby permit it —
  `examination` returns `:no-catalog` for an action the jurisdiction's entry
  is silent on, exactly as it does for a jurisdiction that is missing whole."
  {:exam/question           "質問 — put questions to a person"
   :exam/inspect-books      "検査 — inspect books, records and other items"
   :exam/demand-production  "提示・提出の要求 — demand that items be shown or handed over"
   :exam/field-visit        "実地の調査 — examine at the taxpayer's premises"
   :exam/re-examine         "再調査 — examine a period already examined"
   :exam/contact-third-party "contact someone other than the taxpayer"
   :exam/retain-items       "留置き — keep items that were produced"
   :exam/close-examination  "終了手続 — bring the examination to an end"
   :exam/cross-border-presence "be present at, or participate in, another state's enquiry"
   :exam/joint-audit        "conduct an audit jointly with another state"})

(def facet-universe
  "The dimensions along which a jurisdiction's examination procedure can be
  read. Coverage is reported per facet, not per jurisdiction, because
  `[:us]` read on two facets and `[:jp]` read on eleven are not the same
  thing and one number cannot say so.

  **This set grows when a jurisdiction reveals a question the others were
  never asked.** Reading Germany and Spain added four, and every one of them
  made the previously catalogued jurisdictions score LOWER, because each is a
  question about them that nobody has answered. Coverage going down on new
  knowledge is the correct behaviour; a denominator that only ever grew with
  the numerator would be measuring effort, not ignorance."
  #{:exam/impartiality          ; must the examiner weigh facts both ways? (DE 199(1))
    :exam/duration-limit        ; is there a maximum duration?             (ES 150(1))
    :exam/premises-entry        ; what is required to enter premises?      (ES 142(2), DE 200(3))
    :exam/commencement-information ; what must the taxpayer be told at the start?
    :exam/power-basis
    :exam/criminal-purpose
    :exam/advance-notice
    :exam/notice-contents
    :exam/notice-exception
    :exam/scope-limit
    :exam/repeat-inspection
    :exam/representation
    :exam/third-party-contact
    :exam/identification
    :exam/retention-of-items
    :exam/closing-procedure
    :exam/refusal-sanction
    :exam/cross-border})

;; ---------------------------------------------------------------------------
;; The catalog
;;
;; A requirement is a map. `:req/when` decides whether it applies at all;
;; `:req/test` decides whether the supplied record establishes it. Both are
;; data, not functions, so the whole catalog can be printed, diffed and
;; reviewed by someone who does not read Clojure.
;;
;;   [:always]                     always applies
;;   [:fact-true  :k]              applies / satisfied when facts have k truthy
;;   [:fact-false :k]              applies / satisfied when facts have k present and falsey
;;   [:fact-absent :k]             applies when facts do not carry k at all
;;   [:not <clause>]               negation, used for exceptions
;;   [:any <clause> ...]           disjunction
;;   [:all <clause> ...]           conjunction
;;   [:at-least-days :k n]         facts have k, a number of days, and k >= n
;;   [:at-least :k n] / [:at-most :k n]   generic numeric comparison
;;   [:has-all :k #{...}]          facts have k, a set, containing every member
;;
;; `:req/kind :official-determination` marks a condition the statute commits to
;; a named official's own finding. It is never machine-satisfiable and never
;; becomes `:met` — see `disposition`.
;; ---------------------------------------------------------------------------

(def jp-notice-items
  "国税通則法第七十四条の九第一項 lists SEVEN items, of which the seventh
  delegates to 政令.

  The figure usually quoted in practice is eleven. That figure counts items
  added by 国税通則法施行令第三十条の四 under item seven, together with the
  taxpayer's and the agent's own particulars. Both figures are correct about
  different instruments; only one of them is in the Act, and this catalog has
  read only the Act. `:delegated` is the honest name for the gap."
  {:statutory [:notice/start-datetime      ; 一 調査を開始する日時
               :notice/place               ; 二 調査を行う場所
               :notice/purpose             ; 三 調査の目的
               :notice/tax-items           ; 四 調査の対象となる税目
               :notice/periods             ; 五 調査の対象となる期間
               :notice/records]            ; 六 調査の対象となる帳簿書類その他の物件
   :delegated :notice/cabinet-order-items  ; 七 その他…政令で定める事項
   :statutory-count 7
   :read-count 6
   :commonly-quoted-count 11
   :commonly-quoted-source "国税通則法施行令第三十条の四 — NOT READ by this catalog"})

(def jurisdictions
  "jurisdiction path -> {:facets {...} :actions {...} :out-of-scope {...}}"
  {[:jp]
   {:name "日本"
    :authority "国税庁・国税局・税務署（及び税関）"
    :facets
    {:exam/power-basis        {:facet/status :read :facet/sources [:jp-kokuzei-74-2-1]}
     :exam/criminal-purpose   {:facet/status :read :facet/sources [:jp-kokuzei-74-8]}
     :exam/advance-notice     {:facet/status :read :facet/sources [:jp-kokuzei-74-9-1]}
     :exam/notice-contents    {:facet/status :partly-read :facet/sources [:jp-kokuzei-74-9-1]
                               :facet/note "六 of seven items read; item 七 delegates to 政令 which this catalog has not read"}
     :exam/notice-exception   {:facet/status :read :facet/sources [:jp-kokuzei-74-10]}
     :exam/scope-limit        {:facet/status :read :facet/sources [:jp-kokuzei-74-9-4]}
     :exam/repeat-inspection  {:facet/status :read :facet/sources [:jp-kokuzei-74-11-5]}
     :exam/representation     {:facet/status :read :facet/sources [:jp-kokuzei-74-9-1]
                               :facet/note "税務代理人 must receive the same notice; 国税通則法 does not suspend questioning on a request to consult"}
     :exam/third-party-contact {:facet/status :silent :facet/sources []}
     :exam/identification     {:facet/status :read :facet/sources [:jp-kokuzei-74-13]}
     :exam/retention-of-items {:facet/status :read :facet/sources [:jp-kokuzei-74-7]}
     :exam/closing-procedure  {:facet/status :read :facet/sources [:jp-kokuzei-74-11-1 :jp-kokuzei-74-11-2 :jp-kokuzei-74-11-3]}
     :exam/refusal-sanction   {:facet/status :read :facet/sources [:jp-kokuzei-128]}
     :exam/cross-border       {:facet/status :silent :facet/sources []
                               :facet/note "租税条約・BEPS MLI・実施特例法に基づく情報交換は存在するが、この catalog はまだ読んでいない。silent であって out-of-scope ではない —— 除外の決定はしていない。"}}
    :actions
    {:exam/question
     [{:req/id :jp/necessity :req/facet :exam/power-basis :req/source :jp-kokuzei-74-2-1
       :req/summary "調査について必要があるとき — the officer's own finding of necessity"
       :req/kind :official-determination :req/when [:always]}
      {:req/id :jp/not-criminal-investigation :req/facet :exam/criminal-purpose
       :req/source :jp-kokuzei-74-8
       :req/summary "権限は犯罪捜査のために認められたものと解してはならない"
       :req/when [:always] :req/test [:fact-false :criminal-investigation?]}
      {:req/id :jp/identification :req/facet :exam/identification :req/source :jp-kokuzei-74-13
       :req/summary "身分証明書を携帯し、請求があつたときは提示"
       :req/when [:always] :req/test [:fact-true :identification-carried?]}
      {:req/id :jp/advance-notice :req/facet :exam/advance-notice :req/source :jp-kokuzei-74-9-1
       :req/summary "実地の調査は、あらかじめ納税義務者（及び税務代理人）へ事前通知"
       :req/when [:all [:fact-true :field-visit?]
                       [:not [:fact-true :outside-notified-scope?]]]
       :req/test [:fact-true :advance-notice-given?]
       :req/excused-by :jp/notice-exception}
      {:req/id :jp/notice-exception :req/facet :exam/notice-exception :req/source :jp-kokuzei-74-10
       :req/summary "違法又は不当な行為を容易にし…おそれがあると認める場合には通知を要しない"
       :req/kind :official-determination
       :req/when [:all [:fact-true :field-visit?] [:fact-false :advance-notice-given?]]}
      {:req/id :jp/notice-contents :req/facet :exam/notice-contents :req/source :jp-kokuzei-74-9-1
       :req/summary "通知は第一号から第六号までの事項を含む（第七号は政令）"
       :req/when [:all [:fact-true :field-visit?] [:fact-true :advance-notice-given?]]
       :req/test [:has-all :notice-items #{:notice/start-datetime :notice/place :notice/purpose
                                           :notice/tax-items :notice/periods :notice/records}]}
      {:req/id :jp/notice-cabinet-order-items :req/facet :exam/notice-contents
       :req/source :jp-kokuzei-74-9-1
       :req/summary "第七号「その他調査の適正かつ円滑な実施に必要なものとして政令で定める事項」 — 国税通則法施行令第三十条の四は未読"
       :req/kind :unread-instrument
       :req/when [:all [:fact-true :field-visit?] [:fact-true :advance-notice-given?]]}
      {:req/id :jp/scope-widening-allowed :req/facet :exam/scope-limit :req/source :jp-kokuzei-74-9-4
       :req/summary "非違が疑われる事項については、事前通知の規定は適用しない"
       :req/kind :note :req/when [:fact-true :outside-notified-scope?]}]

     :exam/inspect-books     :exam/question
     :exam/demand-production :exam/question
     :exam/field-visit       :exam/question

     :exam/re-examine
     [{:req/id :jp/new-information :req/facet :exam/repeat-inspection :req/source :jp-kokuzei-74-11-5
       :req/summary "新たに得られた情報に照らし非違があると認めるとき"
       :req/kind :official-determination :req/when [:always]}
      {:req/id :jp/not-criminal-investigation :req/facet :exam/criminal-purpose
       :req/source :jp-kokuzei-74-8
       :req/summary "権限は犯罪捜査のために認められたものと解してはならない"
       :req/when [:always] :req/test [:fact-false :criminal-investigation?]}]

     :exam/retain-items
     [{:req/id :jp/retention-necessity :req/facet :exam/retention-of-items :req/source :jp-kokuzei-74-7
       :req/summary "国税の調査について必要があるとき、当該調査において提出された物件を留め置くことができる"
       :req/kind :official-determination :req/when [:always]}
      {:req/id :jp/produced-in-this-examination :req/facet :exam/retention-of-items
       :req/source :jp-kokuzei-74-7
       :req/summary "留置きの対象は「当該調査において提出された物件」に限る"
       :req/when [:always] :req/test [:fact-true :produced-in-this-examination?]}]

     :exam/close-examination
     [{:req/id :jp/no-correction-notice :req/facet :exam/closing-procedure
       :req/source :jp-kokuzei-74-11-1
       :req/summary "更正決定等をすべきと認められない場合は、その旨を書面により通知"
       :req/when [:all [:fact-true :field-visit?] [:fact-false :correction-intended?]]
       :req/test [:fact-true :written-no-correction-notice?]}
      {:req/id :jp/explain-result :req/facet :exam/closing-procedure :req/source :jp-kokuzei-74-11-2
       :req/summary "更正決定等をすべきと認める場合は、調査結果の内容（額及び理由を含む）を説明"
       :req/when [:fact-true :correction-intended?]
       :req/test [:fact-true :result-explained?]}
      {:req/id :jp/amended-return-writing :req/facet :exam/closing-procedure
       :req/source :jp-kokuzei-74-11-3
       :req/summary "修正申告を勧奨する場合は、不服申立てはできないが更正の請求はできる旨を説明し、その旨を記載した書面を交付しなければならない"
       :req/when [:fact-true :amended-return-urged?]
       :req/test [:fact-true :appeal-rights-document-given?]}]}
    :out-of-scope {}}

   [:us]
   {:name "United States (federal)"
    :authority "Internal Revenue Service"
    :facets
    {:exam/power-basis        {:facet/status :read :facet/sources [:us-irc-7602-a]}
     :exam/criminal-purpose   {:facet/status :read :facet/sources [:us-irc-7602-b :us-irc-7602-d]}
     :exam/advance-notice     {:facet/status :read :facet/sources []
                               :facet/note "read and found ABSENT — see catalog-verification :us-no-general-advance-notice"}
     :exam/notice-contents    {:facet/status :out-of-scope :facet/sources []
                               :facet/note "no general advance notice exists, so it has no contents"}
     :exam/notice-exception   {:facet/status :out-of-scope :facet/sources []}
     :exam/scope-limit        {:facet/status :read :facet/sources [:us-irc-7605-a]}
     :exam/repeat-inspection  {:facet/status :read :facet/sources [:us-irc-7605-b]}
     :exam/representation     {:facet/status :read :facet/sources [:us-irc-7521-b2 :us-irc-7521-a1]}
     :exam/commencement-information {:facet/status :read :facet/sources [:us-irc-7521-b1]}
     :exam/third-party-contact {:facet/status :read :facet/sources [:us-irc-7602-c :us-irc-7602-c-3]}
     :exam/identification     {:facet/status :silent :facet/sources []}
     :exam/retention-of-items {:facet/status :silent :facet/sources []}
     :exam/closing-procedure  {:facet/status :silent :facet/sources []}
     :exam/refusal-sanction   {:facet/status :silent :facet/sources []}
     :exam/cross-border       {:facet/status :silent :facet/sources []}}
    :actions
    {:exam/question
     [{:req/id :us/purpose :req/facet :exam/power-basis :req/source :us-irc-7602-a
       :req/summary "for the purpose of ascertaining the correctness of any return, … determining the liability … or collecting any such liability"
       :req/kind :official-determination :req/when [:always]}
      {:req/id :us/no-doj-referral :req/facet :exam/criminal-purpose :req/source :us-irc-7602-d
       :req/summary "no summons may be issued if a Justice Department referral is in effect"
       :req/when [:fact-true :summons?] :req/test [:fact-false :doj-referral-in-effect?]}
      {:req/id :us/explain-audit-process :req/facet :exam/commencement-information :req/source :us-irc-7521-b1
       :req/summary "before or at an initial interview, explain the audit process and the taxpayer's rights"
       :req/when [:all [:fact-true :in-person-interview?] [:fact-true :initial-interview?]
                       [:not [:fact-true :criminal-investigation?]]]
       :req/test [:fact-true :process-explained?]}
      {:req/id :us/suspend-on-consultation :req/facet :exam/representation :req/source :us-irc-7521-b2
       :req/summary "on a clear statement that the taxpayer wishes to consult a representative, suspend the interview"
       :req/when [:all [:fact-true :consultation-requested?]
                       [:not [:fact-true :summons?]]
                       [:not [:fact-true :criminal-investigation?]]]
       :req/test [:fact-true :interview-suspended?]}
      {:req/id :us/allow-recording :req/facet :exam/representation :req/source :us-irc-7521-a1
       :req/summary "on advance request, allow the taxpayer to record the in-person interview"
       :req/when [:all [:fact-true :in-person-interview?] [:fact-true :recording-requested?]
                       [:not [:fact-true :criminal-investigation?]]]
       :req/test [:fact-true :recording-allowed?]}
      {:req/id :us/reasonable-time-place :req/facet :exam/scope-limit :req/source :us-irc-7605-a
       :req/summary "time and place shall be … reasonable under the circumstances"
       :req/kind :official-determination :req/when [:always]}
      {:req/id :us/summons-10-days :req/facet :exam/scope-limit :req/source :us-irc-7605-a
       :req/summary "date fixed for appearance shall not be less than 10 days from the date of the summons"
       :req/when [:fact-true :summons?] :req/test [:at-least-days :summons-notice-days 10]}]

     :exam/inspect-books     :exam/question
     :exam/demand-production :exam/question
     :exam/field-visit       :exam/question

     :exam/re-examine
     [{:req/id :us/one-inspection :req/facet :exam/repeat-inspection :req/source :us-irc-7605-b
       :req/summary "only one inspection of a taxpayer's books of account shall be made for each taxable year unless the taxpayer requests otherwise or unless the Secretary, after investigation, notifies the taxpayer in writing that an additional inspection is necessary"
       :req/when [:always]
       :req/test [:any [:fact-true :taxpayer-requested-additional?]
                       [:fact-true :written-additional-inspection-notice?]]}
      {:req/id :us/not-unnecessary :req/facet :exam/repeat-inspection :req/source :us-irc-7605-b
       :req/summary "no taxpayer shall be subjected to unnecessary examination or investigations"
       :req/kind :official-determination :req/when [:always]}]

     :exam/contact-third-party
     [{:req/id :us/purpose :req/facet :exam/power-basis :req/source :us-irc-7602-a
       :req/summary "the contact must be for a §7602(a) purpose — the officer's own determination"
       :req/kind :official-determination :req/when [:always]}
      {:req/id :us/genuine-intent-to-contact :req/facet :exam/third-party-contact
       :req/source :us-irc-7602-c-1-intent
       :req/summary "a notice may not be issued unless there is, at the time of issue, an actual intent to contact third parties in that period"
       :req/kind :official-determination
       :req/when [:fact-true :third-party-notice-given?]}
      {:req/id :us/third-party-notice :req/facet :exam/third-party-contact :req/source :us-irc-7602-c
       :req/summary "notice naming a period of not more than 1 year, given not later than 45 days before that period begins"
       :req/when [:all [:not [:fact-true :taxpayer-authorized-contact?]]
                       [:not [:fact-true :pending-criminal-investigation?]]]
       :req/test [:all [:fact-true :third-party-notice-given?]
                       [:at-least-days :third-party-notice-days 45]
                       [:fact-true :contact-within-noticed-period?]]
       :req/excused-by :us/third-party-notice-exception}
      {:req/id :us/third-party-notice-exception :req/facet :exam/third-party-contact
       :req/source :us-irc-7602-c-3
       :req/summary "the Secretary determines for good cause shown that such notice would jeopardize collection or may involve reprisal"
       :req/kind :official-determination
       :req/when [:all [:fact-false :third-party-notice-given?]
                       [:not [:fact-true :taxpayer-authorized-contact?]]
                       [:not [:fact-true :pending-criminal-investigation?]]]}]}
    :out-of-scope
    {:exam/notice-contents
     {:reason "There is no general advance notice of examination in the Internal
               Revenue Code, so there is no statutory content for one. The
               Internal Revenue Manual prescribes contact procedures; the IRM is
               not law and this catalog has not read it."
      :status :nothing-to-read}
     :exam/notice-exception
     {:reason "An exception to a requirement that does not exist."
      :status :nothing-to-read}}}

   [:eu]
   {:name "European Union"
    :authority "— none. The Union has no tax examination authority."
    :facets
    {:exam/power-basis        {:facet/status :out-of-scope :facet/sources []
                               :facet/note "no EU body may examine a taxpayer"}
     :exam/criminal-purpose   {:facet/status :out-of-scope :facet/sources []}
     :exam/advance-notice     {:facet/status :out-of-scope :facet/sources []}
     :exam/notice-contents    {:facet/status :out-of-scope :facet/sources []}
     :exam/notice-exception   {:facet/status :out-of-scope :facet/sources []}
     :exam/scope-limit        {:facet/status :out-of-scope :facet/sources []}
     :exam/repeat-inspection  {:facet/status :out-of-scope :facet/sources []}
     :exam/representation     {:facet/status :out-of-scope :facet/sources []}
     :exam/third-party-contact {:facet/status :out-of-scope :facet/sources []}
     :exam/identification     {:facet/status :out-of-scope :facet/sources []}
     :exam/retention-of-items {:facet/status :out-of-scope :facet/sources []}
     :exam/closing-procedure  {:facet/status :out-of-scope :facet/sources []}
     :exam/refusal-sanction   {:facet/status :out-of-scope :facet/sources []}
     :exam/cross-border       {:facet/status :read
                               :facet/sources [:eu-dac-11-1 :eu-dac-12-1 :eu-dac-12a-1 :eu-dac-12a-2]}}
    :actions
    {:exam/cross-border-presence
     [{:req/id :eu/host-procedural-arrangements :req/facet :exam/cross-border :req/source :eu-dac-11-1
       :req/summary "officials act 'in accordance with the procedural arrangements laid down by' the requested Member State"
       :req/when [:always] :req/test [:fact-true :host-arrangements-followed?]}
      {:req/id :eu/requested-authority-agreed :req/facet :exam/cross-border :req/source :eu-dac-11-1
       :req/summary "the requested authority confirms its agreement (or gives a reasoned refusal) within 60 days"
       :req/when [:always] :req/test [:fact-true :requested-authority-agreed?]}]

     :exam/joint-audit
     [{:req/id :eu/joint-audit-agreed :req/facet :exam/cross-border :req/source :eu-dac-12a-1
       :req/summary "the requested competent authorities respond within 60 days and may reject on justified grounds"
       :req/when [:always] :req/test [:fact-true :requested-authority-agreed?]}
      {:req/id :eu/host-law-governs :req/facet :exam/cross-border :req/source :eu-dac-12a-2
       :req/summary "conducted in accordance with the laws and procedural requirements of the Member State where the activities take place"
       :req/when [:always] :req/test [:fact-true :host-arrangements-followed?]}
      {:req/id :eu/home-power-ceiling :req/facet :exam/cross-border :req/source :eu-dac-12a-2
       :req/summary "officials of another Member State shall not exercise any powers that would exceed the scope of the powers granted to them under the laws of their Member State"
       :req/kind :two-jurisdiction
       :req/when [:always]}]}
    :out-of-scope-default
    {:reason "The European Union has no tax examination authority at all, so
              every facet of examination procedure is out of scope here rather
              than unread. What the Union has is cooperation, catalogued under
              :exam/cross-border."
     :status :nothing-to-read}
    :out-of-scope
    {:exam/power-basis
     {:reason "Directive 2011/16/EU confers cooperation, not examination. Every
               article that touches an actual enquiry routes the power back to a
               Member State. There is no EU-level power to examine a taxpayer to
               catalogue, and inventing one would be the most consequential
               error this library could make."
      :status :nothing-to-read}}}

   [:eu :de]
   {:name "Bundesrepublik Deutschland"
    :authority "Finanzbehörden (Außenprüfung, §§ 193–203 AO)"
    :facets
    {:exam/power-basis        {:facet/status :read :facet/sources [:de-ao-193-1 :de-ao-193-2]
                               :facet/note "admissibility is a GATE, not a purpose: a field audit of a taxpayer outside § 193(1) is inadmissible unless one of § 193(2)'s three conditions holds"}
     :exam/impartiality       {:facet/status :read :facet/sources [:de-ao-199-1]}
     :exam/advance-notice     {:facet/status :read :facet/sources [:de-ao-197-1 :de-ao-197-2]}
     :exam/notice-contents    {:facet/status :read :facet/sources [:de-ao-196 :de-ao-197-1]}
     :exam/notice-exception   {:facet/status :read :facet/sources [:de-ao-197-1]
                               :facet/note "inline in the same sentence — wenn der Prüfungszweck dadurch nicht gefährdet wird — not a separate article as in JP 74-10"}
     :exam/commencement-information {:facet/status :partly-read :facet/sources [:de-ao-197-1]
                                     :facet/note "the order, expected start and auditors' names are announced; AO does not require an explanation of the taxpayer's rights the way ES 147(2) and US 7521(b)(1) do"}
     :exam/identification     {:facet/status :read :facet/sources [:de-ao-198]}
     :exam/premises-entry     {:facet/status :read :facet/sources [:de-ao-200-3]}
     :exam/criminal-purpose   {:facet/status :read :facet/sources [:de-ao-201-2]
                               :facet/note "neither JP's prohibition nor US's inclusion — the criminal assessment is RESERVED to a separate procedure and the taxpayer should be told so"}
     :exam/closing-procedure  {:facet/status :read :facet/sources [:de-ao-201-1 :de-ao-202-1 :de-ao-202-2 :de-ao-199-2]}
     :exam/scope-limit        {:facet/status :partly-read :facet/sources [:de-ao-196]
                               :facet/note "§ 194 defines the material scope and has not been read into requirements"}
     :exam/representation     {:facet/status :silent :facet/sources []
                               :facet/note "§ 80 AO governs Bevollmächtigte generally and has not been read; §§ 193–203 contain no interview-suspension right"}
     :exam/repeat-inspection  {:facet/status :silent :facet/sources []
                               :facet/note "§ 173 Abs. 2 Änderungssperre and the BFH case law are outside the range read"}
     :exam/retention-of-items {:facet/status :silent :facet/sources []}
     :exam/refusal-sanction   {:facet/status :silent :facet/sources []
                               :facet/note "§ 200a qualifiziertes Mitwirkungsverlangen and §§ 328 ff Zwangsmittel not read"}
     :exam/third-party-contact {:facet/status :silent :facet/sources []}
     :exam/duration-limit     {:facet/status :silent :facet/sources []}
     :exam/cross-border       {:facet/status :silent :facet/sources []
                               :facet/note "supplied by the [:eu] level — see effective-facets"}}
    :actions
    {:exam/field-visit
     [{:req/id :de/admissible-taxpayer :req/facet :exam/power-basis :req/source :de-ao-193-1
       :req/summary "Außenprüfung ist zulässig bei gewerblichen / land- und forstwirtschaftlichen / freiberuflichen Steuerpflichtigen und § 147a-Fällen"
       :req/when [:always]
       :req/test [:any [:fact-true :business-or-professional?]
                       [:fact-true :withholding-agent?]
                       [:fact-true :section-193-2-condition?]]}
      {:req/id :de/written-order :req/facet :exam/notice-contents :req/source :de-ao-196
       :req/summary "Umfang in einer schriftlich oder elektronisch zu erteilenden Prüfungsanordnung mit Rechtsbehelfsbelehrung"
       :req/when [:always] :req/test [:fact-true :written-audit-order?]}
      {:req/id :de/order-announced-in-advance :req/facet :exam/advance-notice :req/source :de-ao-197-1
       :req/summary "Prüfungsanordnung, voraussichtlicher Prüfungsbeginn und Namen der Prüfer angemessene Zeit vor Beginn bekannt zu geben"
       :req/when [:not [:fact-true :notice-period-waived?]]
       :req/test [:fact-true :order-announced-in-advance?]
       :req/excused-by :de/purpose-jeopardised}
      {:req/id :de/purpose-jeopardised :req/facet :exam/notice-exception :req/source :de-ao-197-1
       :req/summary "wenn der Prüfungszweck dadurch nicht gefährdet wird — the authority's own assessment"
       :req/kind :official-determination
       :req/when [:fact-false :order-announced-in-advance?]}
      {:req/id :de/auditor-names :req/facet :exam/notice-contents :req/source :de-ao-197-1
       :req/summary "die Namen der Prüfer gehören zur Bekanntgabe"
       :req/when [:fact-true :order-announced-in-advance?]
       :req/test [:fact-true :auditor-names-announced?]}
      {:req/id :de/identify-immediately :req/facet :exam/identification :req/source :de-ao-198
       :req/summary "Die Prüfer haben sich bei Erscheinen unverzüglich auszuweisen"
       :req/when [:always] :req/test [:fact-true :identified-on-arrival?]}
      {:req/id :de/record-start-time :req/facet :exam/identification :req/source :de-ao-198
       :req/summary "Der Beginn ist unter Angabe von Datum und Uhrzeit aktenkundig zu machen"
       :req/when [:always] :req/test [:fact-true :start-time-recorded?]}
      {:req/id :de/impartial :req/facet :exam/impartiality :req/source :de-ao-199-1
       :req/summary "zugunsten wie zuungunsten des Steuerpflichtigen zu prüfen"
       :req/kind :conduct-duty :req/when [:always]}
      {:req/id :de/business-hours :req/facet :exam/premises-entry :req/source :de-ao-200-3
       :req/summary "Die Außenprüfung findet während der üblichen Geschäfts- oder Arbeitszeit statt"
       :req/when [:always] :req/test [:fact-true :during-business-hours?]}]

     :exam/question          :exam/field-visit
     :exam/inspect-books     :exam/field-visit
     :exam/demand-production :exam/field-visit

     :exam/close-examination
     [{:req/id :de/closing-meeting :req/facet :exam/closing-procedure :req/source :de-ao-201-1
       :req/summary "Über das Ergebnis ist eine Schlussbesprechung abzuhalten, es sei denn keine Änderung oder Verzicht"
       :req/when [:all [:not [:fact-true :no-change-in-tax-bases?]]
                       [:not [:fact-true :closing-meeting-waived?]]]
       :req/test [:fact-true :closing-meeting-held?]}
      {:req/id :de/criminal-warning :req/facet :exam/criminal-purpose :req/source :de-ao-201-2
       :req/summary "bei möglichem Straf- oder Bußgeldverfahren soll darauf hingewiesen werden, dass die Würdigung einem besonderen Verfahren vorbehalten bleibt"
       :req/when [:fact-true :criminal-proceedings-possible?]
       :req/test [:fact-true :separate-procedure-warning-given?]}
      {:req/id :de/written-report :req/facet :exam/closing-procedure :req/source :de-ao-202-1
       :req/summary "Über das Ergebnis ergeht ein schriftlicher oder elektronischer Prüfungsbericht"
       :req/when [:always] :req/test [:fact-true :written-report-issued?]}
      {:req/id :de/report-before-evaluation :req/facet :exam/closing-procedure :req/source :de-ao-202-2
       :req/summary "auf Antrag den Prüfungsbericht vor seiner Auswertung übersenden und Gelegenheit zur Stellungnahme geben"
       :req/when [:fact-true :report-requested-in-advance?]
       :req/test [:fact-true :report-sent-before-evaluation?]}]}
    :out-of-scope {}}

   [:eu :es]
   {:name "Reino de España"
    :authority "Inspección de los tributos (Ley 58/2003, arts. 141–159)"
    :facets
    {:exam/power-basis        {:facet/status :read :facet/sources [:es-lgt-141]}
     :exam/commencement-information {:facet/status :read :facet/sources [:es-lgt-147-2]}
     :exam/premises-entry     {:facet/status :read :facet/sources [:es-lgt-142-2 :es-lgt-151-3 :es-lgt-152-2]}
     :exam/duration-limit     {:facet/status :read :facet/sources [:es-lgt-150-1]}
     :exam/repeat-inspection  {:facet/status :partly-read :facet/sources [:es-lgt-148-3]
                               :facet/note "the exception routes to art 101.4.a), which this catalog has not read"}
     :exam/closing-procedure  {:facet/status :read :facet/sources [:es-lgt-156-1 :es-lgt-157-1 :es-lgt-157-2]}
     :exam/identification     {:facet/status :read :facet/sources [:es-lgt-34-1-f]
                               :facet/note "framed as a taxpayer RIGHT to know the identity, not as a duty to show a card on appearing (contrast DE 198, JP 74-13)"}
     :exam/advance-notice     {:facet/status :read :facet/sources [:es-lgt-151-2]
                               :facet/note "read and found to point the other way: the inspection may appear WITHOUT prior communication"}
     :exam/notice-contents    {:facet/status :out-of-scope :facet/sources []}
     :exam/notice-exception   {:facet/status :out-of-scope :facet/sources []}
     :exam/scope-limit        {:facet/status :partly-read :facet/sources [:es-lgt-148-3]}
     :exam/impartiality       {:facet/status :silent :facet/sources []}
     :exam/criminal-purpose   {:facet/status :silent :facet/sources []}
     :exam/representation     {:facet/status :silent :facet/sources []}
     :exam/third-party-contact {:facet/status :silent :facet/sources []}
     :exam/retention-of-items {:facet/status :silent :facet/sources []}
     :exam/refusal-sanction   {:facet/status :silent :facet/sources []}
     :exam/cross-border       {:facet/status :silent :facet/sources []}}
    :actions
    {:exam/field-visit
     [{:req/id :es/inspection-function :req/facet :exam/power-basis :req/source :es-lgt-141
       :req/summary "el ejercicio de las funciones administrativas de investigación y comprobación"
       :req/kind :official-determination :req/when [:always]}
      {:req/id :es/commencement-information :req/facet :exam/commencement-information
       :req/source :es-lgt-147-2
       :req/summary "informar al inicio sobre la naturaleza y alcance, así como de sus derechos y obligaciones"
       :req/when [:always] :req/test [:fact-true :commencement-information-given?]}
      {:req/id :es/no-prior-communication-needed :req/facet :exam/advance-notice
       :req/source :es-lgt-151-2
       :req/summary "la inspección podrá personarse sin previa comunicación"
       :req/kind :note :req/when [:always]}
      {:req/id :es/entry-authorisation :req/facet :exam/premises-entry :req/source :es-lgt-142-2
       :req/summary "si el custodio se opusiera a la entrada, se precisará la autorización escrita de la autoridad administrativa"
       :req/when [:fact-true :entry-opposed?]
       :req/test [:fact-true :written-entry-authorisation?]}
      {:req/id :es/protected-domicile :req/facet :exam/premises-entry :req/source :es-lgt-142-2
       :req/summary "domicilio constitucionalmente protegido — se aplicará lo dispuesto en el artículo 113, que este catálogo no ha leído"
       :req/kind :unread-instrument
       :req/when [:fact-true :constitutionally-protected-domicile?]}
      {:req/id :es/books-at-taxpayer-premises :req/facet :exam/premises-entry :req/source :es-lgt-151-3
       :req/summary "los libros deberán ser examinados en el domicilio del obligado, en su presencia, salvo que consienta su examen en oficinas públicas"
       :req/when [:fact-true :books-examined-at-public-office?]
       :req/test [:fact-true :taxpayer-consented-to-office-examination?]}
      {:req/id :es/working-hours :req/facet :exam/premises-entry :req/source :es-lgt-152-2
       :req/summary "se respetará la jornada laboral, salvo actuación de común acuerdo en otras horas o días"
       :req/when [:always]
       :req/test [:any [:fact-true :during-business-hours?] [:fact-true :out-of-hours-agreed?]]}
      {:req/id :es/twelve-month-limit :req/facet :exam/duration-limit :req/source :es-lgt-150-1
       :req/summary "las actuaciones deberán concluir en el plazo de 12 meses desde la notificación del inicio"
       :req/when [:always]
       :req/test [:any [:at-most :elapsed-months 12] [:fact-true :extension-granted?]]}
      {:req/id :es/extension-reasoned :req/facet :exam/duration-limit :req/source :es-lgt-150-1
       :req/summary "los acuerdos de ampliación serán, en todo caso, motivados, y no podrán exceder de otros 12 meses"
       :req/when [:fact-true :extension-granted?]
       :req/test [:all [:fact-true :extension-reasoned?] [:at-most :elapsed-months 24]]}]

     :exam/question          :exam/field-visit
     :exam/inspect-books     :exam/field-visit
     :exam/demand-production :exam/field-visit

     :exam/re-examine
     [{:req/id :es/inspection-function :req/facet :exam/power-basis :req/source :es-lgt-141
       :req/summary "el ejercicio de las funciones administrativas de investigación y comprobación"
       :req/kind :official-determination :req/when [:always]}
      {:req/id :es/provisional-liquidation-bar :req/facet :exam/repeat-inspection
       :req/source :es-lgt-148-3
       :req/summary "terminadas con liquidación provisional, el objeto no podrá regularizarse nuevamente"
       :req/when [:fact-true :ended-with-provisional-liquidation?]
       :req/test [:fact-false :same-object?]}
      {:req/id :es/art-101-4-a-exception :req/facet :exam/repeat-inspection
       :req/source :es-lgt-148-3
       :req/summary "salvo que concurra alguna de las circunstancias del artículo 101.4.a), que este catálogo no ha leído"
       :req/kind :unread-instrument
       :req/when [:all [:fact-true :ended-with-provisional-liquidation?] [:fact-true :same-object?]]}]

     :exam/close-examination
     [{:req/id :es/hearing-before-acta :req/facet :exam/closing-procedure :req/source :es-lgt-156-1
       :req/summary "con carácter previo a la firma del acta se concederá trámite de audiencia"
       :req/when [:always] :req/test [:fact-true :hearing-granted?]}
      {:req/id :es/disconformity-report :req/facet :exam/closing-procedure :req/source :es-lgt-157-2
       :req/summary "en disconformidad, se acompañará un informe del actuario con los fundamentos de derecho"
       :req/when [:fact-true :taxpayer-disagrees?]
       :req/test [:fact-true :actuary-report-attached?]}]}
    :out-of-scope
    {:exam/notice-contents
     {:reason "Art 151.2 lets the inspection appear without prior communication,
               so there is no statutory advance notice for which contents could
               be prescribed. Art 147.2 prescribes what must be said AT the
               start, which is :exam/commencement-information, not this."
      :status :nothing-to-read}
     :exam/notice-exception
     {:reason "An exception to a requirement that does not exist."
      :status :nothing-to-read}}}})

;; ---------------------------------------------------------------------------
;; Clause evaluation
;; ---------------------------------------------------------------------------

(def ^:private tri-and
  {[:yes :yes] :yes   [:yes :no] :no   [:yes :unknown] :unknown
   [:no :yes] :no     [:no :no] :no    [:no :unknown] :no
   [:unknown :yes] :unknown [:unknown :no] :no [:unknown :unknown] :unknown})

(def ^:private tri-or
  {[:yes :yes] :yes   [:yes :no] :yes  [:yes :unknown] :yes
   [:no :yes] :yes    [:no :no] :no    [:no :unknown] :unknown
   [:unknown :yes] :yes [:unknown :no] :unknown [:unknown :unknown] :unknown})

(defn- tri-not [v] (case v :yes :no, :no :yes, :unknown))

(defn eval-clause
  "Evaluate a catalog clause against a fact map. Three-valued on purpose:
  `:unknown` is the answer when the record does not say, and it must never
  collapse into `:no` for a `:req/test` (that would read *nobody wrote this
  down* as *this was not done*, which is the same class of error as reading
  an uncatalogued jurisdiction as permitted)."
  [clause facts]
  (let [[op a b] clause]
    (case op
      :always :yes
      :fact-true    (if (contains? facts a) (if (get facts a) :yes :no) :unknown)
      :fact-false   (if (contains? facts a) (if (get facts a) :no :yes) :unknown)
      :fact-absent  (if (contains? facts a) :no :yes)
      :not          (tri-not (eval-clause a facts))
      :any          (reduce #(get tri-or [%1 (eval-clause %2 facts)])
                            :no (rest clause))
      :all          (reduce #(get tri-and [%1 (eval-clause %2 facts)])
                            :yes (rest clause))
      :at-least     (let [v (get facts a)]
                      (cond (not (contains? facts a)) :unknown
                            (not (number? v)) :unknown
                            (>= v b) :yes
                            :else :no))
      :at-most      (let [v (get facts a)]
                      (cond (not (contains? facts a)) :unknown
                            (not (number? v)) :unknown
                            (<= v b) :yes
                            :else :no))
      :at-least-days (let [v (get facts a)]
                       (cond (not (contains? facts a)) :unknown
                             (not (number? v)) :unknown
                             (>= v b) :yes
                             :else :no))
      :has-all      (let [v (get facts a)]
                      (cond (not (contains? facts a)) :unknown
                            (not (coll? v)) :unknown
                            (every? (set v) b) :yes
                            :else :no))
      :unknown)))

;; ---------------------------------------------------------------------------
;; Lookup
;; ---------------------------------------------------------------------------

(defn- normalize [j]
  (cond (keyword? j) [j]
        (sequential? j) (vec j)
        :else j))

(defn levels
  "Jurisdictions are PATHS, not codes, and rules attach at a level.

      [:eu :de]  ->  [[:eu] [:eu :de]]

  A German field audit is governed by German law; the same officer sitting in
  a Spanish joint audit is additionally capped by Directive 2011/16/EU. Both
  levels are read and the more specific one wins where they overlap."
  [j]
  (let [p (normalize j)]
    (mapv #(vec (take % p)) (range 1 (inc (count p))))))

(defn jurisdiction
  "The catalog entry for THIS EXACT level, or nil. nil means NOT READ, never
  NO REQUIREMENTS. For the merged view of a path use `effective-facets`."
  [j]
  (get jurisdictions (normalize j)))

(defn catalogued-levels [j] (filterv #(contains? jurisdictions %) (levels j)))
(defn unchecked-levels  [j] (filterv #(not (contains? jurisdictions %)) (levels j)))

(def ^:private informative? #{:read :partly-read})

(defn effective-facets
  "Facet statuses for a path. The most specific level wins, with one exception
  in each direction, and both exceptions were found by a test.

  **A parent contributes only the facets it actually read.** The European Union
  marks thirteen facets `:out-of-scope` because the Union has no examination
  power — that is a statement about the Union, not about Germany. Letting it
  propagate would report German re-examination law as deliberately out of scope
  when in truth nobody has read it. So `:out-of-scope` and `:silent` stop at the
  level that declared them.

  **And a child's `:silent` does not overwrite a parent's `:read`.** `:silent`
  means *this level says nothing*, which cannot outrank *that level said
  something*. Germany's own entry is silent on cross-border because the
  Directive is where that law lives; the merged view must still read
  `:read`, sourced from `[:eu]`. A child's `:out-of-scope` DOES win, because
  that is a decision rather than an absence.

  Each entry carries `:facet/from`, the level that supplied it."
  [j]
  (let [ls (catalogued-levels j)
        own (last ls)
        stamp (fn [l m] (into {} (map (fn [[k v]] [k (assoc v :facet/from l)])) m))
        base (stamp own (:facets (get jurisdictions own)))]
    (reduce (fn [acc l]
              (let [f (stamp l (:facets (get jurisdictions l)))]
                (reduce-kv (fn [a k v]
                             (if (and (informative? (:facet/status v))
                                      (not (informative? (get-in a [k :facet/status]))))
                               ;; keep the child's note if it had one to give
                               (assoc a k (merge v (select-keys (get a k) [:facet/note])))
                               a))
                           acc f)))
            base
            (reverse (butlast ls)))))

(defn covered?
  "Is this EXACT level in the catalog?

  Deliberately not level-aware: `[:eu :fr]` must not count as covered merely
  because `[:eu]` is. France's examination procedure is unread, and a coverage
  report that said otherwise would be the flattering answer."
  [j]
  (some? (jurisdiction j)))

(defn source [source-id] (get sources source-id))

(defn source-urls []
  (into (sorted-set) (map :source/url) (vals sources)))

(defn law-ids []
  (into (sorted-set) (map :source/law-id) (vals sources)))

(def ^:private normalized-actions
  "Actions may alias another action's requirement list by naming it:

      :exam/inspect-books :exam/question

  Resolved once at load, with a visited set so a cycle in the catalog is an
  error at load rather than a hang at call time."
  (into {}
        (for [[jpath entry] jurisdictions]
          (let [acts (:actions entry)
                resolve* (fn resolve* [k seen]
                           (let [v (get acts k)]
                             (cond
                               (vector? v) v
                               (nil? v) nil
                               (contains? seen k)
                               (throw (ex-info "cyclic action alias in catalog"
                                               {:jurisdiction jpath :action k}))
                               (keyword? v) (resolve* v (conj seen k))
                               :else nil)))]
            [jpath (into {} (for [k (keys acts)
                                  :let [r (resolve* k #{})]
                                  :when r]
                              [k r]))]))))

(defn- requirements-for
  "Requirements from every catalogued level of the path, parent first.

  A German officer in a Spanish joint audit answers to both the Directive and
  German law; the requirement list is the union, not the more specific one."
  [j action]
  (let [rs (into [] (comp (map #(get-in normalized-actions [% action]))
                          (remove nil?)
                          cat)
                 (catalogued-levels j))]
    (when (seq rs) rs)))

;; ---------------------------------------------------------------------------
;; The one question
;; ---------------------------------------------------------------------------

(defn examination
  "What does the law of `j` require before `action` may be taken, and which of
  those requirements does `facts` establish?

  Returns a map. When the jurisdiction is not in the catalog, or the catalog
  says nothing about this action, the map has **no `:examlaw/authority` key at
  all** — there is nothing to read as a permission."
  ([j action] (examination j action {}))
  ([j action facts]
   (let [jpath (normalize j)
         cls (catalogued-levels jpath)
         unchecked (unchecked-levels jpath)
         reqs (requirements-for jpath action)
         base {:examlaw/jurisdiction jpath
               :examlaw/action action
               :examlaw/levels-read cls}]
     (cond
       (empty? cls)
       (assoc base :examlaw/coverage :none
              :examlaw/unchecked unchecked
              :examlaw/reason :jurisdiction-not-in-catalog
              :examlaw/requirements [])

       (nil? reqs)
       (assoc base :examlaw/coverage :none
              :examlaw/unchecked (if (seq unchecked) unchecked [jpath])
              :examlaw/reason (if (contains? actions action)
                                :action-not-catalogued-here
                                :unknown-action)
              :examlaw/out-of-scope (:out-of-scope (get jurisdictions (last cls)))
              :examlaw/requirements [])

       :else
       (let [evaluated
             (vec (for [r reqs]
                    (let [applies (eval-clause (:req/when r [:always]) facts)
                          kind (:req/kind r)]
                      (assoc r
                             :req/status
                             (cond
                               (= applies :no) :not-applicable
                               (= kind :note) :note
                               ;; applies is :yes or :unknown here. An unknown does NOT
                               ;; drop the determination: silence about whether a
                               ;; safeguard is engaged is not evidence that it is not.
                               (= kind :official-determination) :official-determination
                               (= kind :two-jurisdiction) :two-jurisdiction
                               ;; a duty on the officer's conduct that no record
                               ;; can establish (DE 199(1): examine for AND against)
                               (= kind :conduct-duty) :conduct-duty
                               ;; the statute routes this to an instrument this
                               ;; catalog has not read (JP 74-9 item 7 -> 政令,
                               ;; ES 142(2) -> art 113). Never a pass.
                               (= kind :unread-instrument) :unread-instrument
                               (nil? (:req/test r)) :unverified
                               :else (case (eval-clause (:req/test r) facts)
                                       :yes :met
                                       :no :unmet
                                       :unknown :unverified))))))
             excused (into #{}
                           (comp (filter #(= :official-determination (:req/status %)))
                                 (map :req/id))
                           evaluated)
             ;; a requirement whose :req/excused-by determination is present is
             ;; not reported as unmet; it is reported as deferred to that official
             evaluated (mapv (fn [r]
                               (if (and (= :unmet (:req/status r))
                                        (contains? excused (:req/excused-by r)))
                                 (assoc r :req/status :deferred-to-determination)
                                 r))
                             evaluated)
             by (group-by :req/status evaluated)]
         (assoc base
                :examlaw/coverage :checked
                :examlaw/unchecked unchecked
                :examlaw/requirements evaluated
                :examlaw/met (mapv :req/id (:met by))
                :examlaw/unmet (mapv :req/id (:unmet by))
                :examlaw/unverified (mapv :req/id (:unverified by))
                :examlaw/official-determination (mapv :req/id (:official-determination by))
                :examlaw/deferred (mapv :req/id (:deferred-to-determination by))
                :examlaw/two-jurisdiction (mapv :req/id (:two-jurisdiction by))
                :examlaw/conduct-duty (mapv :req/id (:conduct-duty by))
                :examlaw/unread-instrument (mapv :req/id (:unread-instrument by))))))))

(defn disposition
  "One of four values. This is the function to read, not `:examlaw/met`.

    :no-catalog                      nothing here was checked
    :blocked                         a catalogued requirement is positively unmet
    :requires-official-determination the statute commits something to a named
                                     official's own finding, or the record does
                                     not establish a requirement
    :no-catalogued-requirement-unmet every catalogued requirement the record
                                     speaks to is satisfied

  The fourth is deliberately not called `:permitted`. It is a statement about
  this catalog, which has read three jurisdictions on fourteen facets. It is
  not a statement about the law, and it is not a decision that an official has
  made."
  [result]
  (cond
    (not= :checked (:examlaw/coverage result)) :no-catalog
    (seq (:examlaw/unmet result)) :blocked
    (or (seq (:examlaw/unverified result))
        (seq (:examlaw/official-determination result))
        (seq (:examlaw/deferred result))
        (seq (:examlaw/two-jurisdiction result))
        (seq (:examlaw/conduct-duty result))
        (seq (:examlaw/unread-instrument result))) :requires-official-determination
    :else :no-catalogued-requirement-unmet))

(defn authorized?
  "Deliberately NOT `(empty? (:examlaw/unmet result))`.

  A caller who reaches for the convenient boolean gets the conservative
  answer. False for an uncatalogued jurisdiction, false while anything is
  unverified, and false whenever the statute leaves a finding to an official —
  because in that case the answer is that official's to give and not this
  library's."
  [result]
  (= :no-catalogued-requirement-unmet (disposition result)))

;; ---------------------------------------------------------------------------
;; Cross-border: the one place where two jurisdictions must both be read
;; ---------------------------------------------------------------------------

(defn joint-audit
  "Article 12a(2) caps a visiting official at the LOWER of two ceilings: the
  host Member State's procedural law, and the powers their own Member State
  grants them. So this takes two jurisdictions and reads both.

  If either is missing from the catalog the answer is `:no-catalog`. An
  intersection with an unread set is not the unread set — it is unknown, and
  reporting the host's rules alone would silently drop the home-state cap that
  the Article exists to impose."
  ([host home action] (joint-audit host home action {}))
  ([host home action facts]
   (let [hostp (normalize host) homep (normalize home)
         eu (examination [:eu] :exam/joint-audit facts)
         h (examination hostp action facts)
         m (examination homep action facts)
         unchecked (vec (concat (:examlaw/unchecked h) (:examlaw/unchecked m)))]
     (if (seq unchecked)
       {:examlaw/coverage :none
        :examlaw/unchecked unchecked
        :examlaw/reason :cross-border-needs-both-jurisdictions
        :examlaw/host hostp :examlaw/home homep :examlaw/action action}
       {:examlaw/coverage :checked
        :examlaw/host hostp :examlaw/home homep :examlaw/action action
        :examlaw/directive eu
        :examlaw/host-result h
        :examlaw/home-result m
        ;; the ceiling is the intersection: blocked by either side blocks
        :examlaw/disposition
        (let [ds (map disposition [eu h m])]
          (cond (some #{:no-catalog} ds) :no-catalog
                (some #{:blocked} ds) :blocked
                (some #{:requires-official-determination} ds) :requires-official-determination
                :else :no-catalogued-requirement-unmet))
        :examlaw/unmet (vec (concat (:examlaw/unmet eu) (:examlaw/unmet h) (:examlaw/unmet m)))}))))

;; ---------------------------------------------------------------------------
;; Coverage — and the denominator the caller has to supply
;; ---------------------------------------------------------------------------

(defn out-of-scope-reason
  "Why a facet was left out on purpose, or nil.

  nil is NOT 'no reason' — for a facet that is not marked `:out-of-scope` there
  is nothing to explain. A facet that IS marked out-of-scope and resolves to
  nil here is a catalog defect, and a test says so."
  [j facet]
  (when (= :out-of-scope (get-in (effective-facets j) [facet :facet/status]))
    (some (fn [l]
            (let [e (get jurisdictions l)]
              (when (= :out-of-scope (get-in e [:facets facet :facet/status]))
                (or (get-in e [:out-of-scope facet]) (:out-of-scope-default e)))))
          (reverse (catalogued-levels j)))))

(defn depth
  "Per-facet partition for one jurisdiction. `:read`, `:partly-read`,
  `:out-of-scope` and `:silent` sum to `:of` — a test asserts it, because two
  buckets once double-counted a facet that was both read and partly out of
  scope."
  [j]
  (when (seq (catalogued-levels j))
    (let [f (effective-facets j)
          by (reduce (fn [acc facet]
                       (let [st (get-in f [facet :facet/status] :silent)]
                         (update acc st (fnil conj []) facet)))
                     {} facet-universe)]
      {:read (count (:read by))
       :partly-read (count (:partly-read by))
       :out-of-scope (count (:out-of-scope by))
       :silent (count (:silent by))
       :of (count facet-universe)
       :facets by})))

(defn world-coverage
  "REQUIRES a universe and has no default.

  The thing being measured is precisely what this catalog does not know about,
  so the denominator has to come from outside it. A firm operating in four
  countries has a universe of four; a treaty secretariat has one of 193. This
  library refuses to pick for them, because picking would make the most
  flattering number the default."
  [universe]
  (when (or (nil? universe) (not (coll? universe)) (empty? universe))
    (throw (ex-info "world-coverage requires a universe and has no default"
                    {:examlaw/reason :no-denominator})))
  (let [u (map normalize universe)
        read (filterv covered? u)
        depths (into {} (for [j read] [j (depth j)]))
        facet-read (reduce + 0 (map (fn [[_ d]] (+ (:read d) (:partly-read d))) depths))]
    {:examlaw/universe (vec (sort-by pr-str u))
     :examlaw/read (vec (sort-by pr-str read))
     :examlaw/unread (vec (sort-by pr-str (remove covered? u)))
     :examlaw/jurisdiction-fraction [(count read) (count u)]
     :examlaw/depth depths
     ;; the figure that does not flatter: facets read out of every facet of
     ;; every jurisdiction in the universe, not just the catalogued ones
     :examlaw/facet-total [facet-read (* (count u) (count facet-universe))]}))
