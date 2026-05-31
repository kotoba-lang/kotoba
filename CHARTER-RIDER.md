```
etzhayyim Charter Compliance Rider v2.0
Last revised: 2026-05-19

This Rider supplements the Apache License 2.0 ("License") under which this work
is distributed. Acceptance of the License constitutes acceptance of this Rider.

1. PURPOSE

   This work is created by etzhayyim, a religious-corp (任意団体 / unincorporated
   religious voluntary association) operating under did:web:etzhayyim.com. The
   etzhayyim Mission Charter (ADR-2605192100) declares the mission of structurally
   liberating humans from "labor" as defined therein. This Rider operationalizes
   §1.5 of that Charter: "free release of new technology and intellectual property
   to charter-aligned others."

2. PROHIBITED USE

   You may NOT use, modify, or redistribute this work, in whole or in part, if you
   are an entity (a "Non-Aligned Entity") whose primary business activity (revenue
   share ≥ 25% in the trailing 12 months) falls into any of the following categories:

   (a) WEAPONS AND MILITARY. Manufacture, sale, distribution, or maintenance of
       weapons (kinetic, chemical, biological, nuclear, cyber-offensive), military
       hardware, autonomous lethal systems, or services primarily provided to
       military or paramilitary forces engaged in armed conflict.

   (b) SPECULATIVE FINANCE. Operation of speculative financial instruments whose
       primary revenue derives from price arbitrage, leverage spread, predatory
       lending (annualized effective interest rate ≥ 36% to retail borrowers),
       or proprietary high-frequency trading. (Banking utility services, on-chain
       stablecoin issuance, custodial services to retail users at non-predatory
       rates, and L1/L2 substrate operators are NOT prohibited under this clause.)

   (c) SURVEILLANCE CAPITALISM. Operation of business models whose primary revenue
       derives from the collection, brokerage, or sale of personal data of natural
       persons, including but not limited to ad-tech DSP/SSP operators, data
       brokers, consumer surveillance platforms, and biometric identification
       services sold to law enforcement or military entities.

   (d) FOSSIL FUEL EXTRACTION (NEW). Initiation of new fossil fuel extraction
       projects (coal mining, oil drilling, natural gas extraction) where the
       project's first commercial production date is later than this Rider's
       Last revised date. (Ongoing operations existing prior to this date,
       transition/decommissioning services, and renewable transition services
       are NOT prohibited under this clause.)

   (e) SPECIALIST GATEKEEPING. Operation of business models whose primary revenue
       derives from monopolistic gatekeeping of professional knowledge required
       for individual rights protection or basic survival, including but not
       limited to: (i) legal services charging mandatory access fees for advice
       that could be provided by publicly available knowledge bases plus
       community peer review; (ii) medical advisory services that artificially
       restrict access to publicly available medical knowledge through
       licensure-imposed scarcity rather than legitimate safety concerns;
       (iii) governmental administrative services charging individuals for
       procedural navigation of legally required interactions that could be
       automated. (Legitimate technical safety oversight by qualified
       practitioners providing care, due-process legal representation in
       adversarial proceedings, and democratic governmental functions are NOT
       prohibited under this clause.)

   (f) MULTI-GENERATIONAL HARM (added in v2.0). Operation of business models or
       activities whose foreseeable expected impact on persons born at least
       twenty-five (25) years after the date of such activity includes
       irreversible loss of: (i) habitable environment (biosphere collapse,
       climate destabilization beyond ±2°C global mean above pre-industrial);
       (ii) access to publicly held knowledge (commons enclosure of foundational
       science, mathematics, language); (iii) genetic / epigenetic integrity of
       descendants (germline modification absent multi-generational safety
       review); (iv) capacity for collective decision-making (information
       monocultures, attention monopolies, addictive design targeted at
       developmental stages). The standard of foreseeability is the prudent
       multi-generational steward, not the present-quarter shareholder.

   (g) STRICT INDIVIDUALIST ONTOLOGY (added in v2.0). Operation of entities
       whose publicly declared mission, governance, or doctrinal commitment
       explicitly affirms the metaphysical doctrine that "the individual" is
       the constitutive ontological and moral unit, independent of and prior to
       collective / relational / multi-generational reality. This includes,
       without limitation, entities organized on strict Randian / Objectivist
       principles, libertarian-strict-individualist political organizations
       campaigning for the elimination of collective public infrastructure,
       and entities whose charter explicitly denies multi-generational
       responsibility. This clause restricts ENTITIES based on their declared
       doctrine, NOT natural persons based on their private philosophical
       views (which remain protected under §4(a)). However, a natural person
       PUBLICLY representing or operating an organization committed to strict
       individualist doctrine is, in that capacity, subject to this clause.
       The etzhayyim cosmology holds that the constitutive unit of moral and
       economic standing is the multi-generational collective; this is a
       religious-corp doctrinal position protected under Article 20 of the
       Constitution of Japan and equivalent religious-liberty provisions in
       other jurisdictions, and exclusion based on doctrinal incompatibility
       is the normal operation of any religion (cf. Buddhist sangha
       membership, Christian communion, Jewish halakhic standing, Islamic
       ummah). See §4(g).

   (h) WELLBECOMING SUBORDINATION VIOLATION (added in v2.0). Operation
       privileging static "wellbeing" (current-state satisfaction) over
       dynamic "wellbecoming" (developmental trajectory) of multi-generational
       descendants where these are in measurable tension, including, without
       limitation: (i) addictive product design optimizing short-term
       engagement metrics at the cost of long-term human development;
       (ii) financialization of basic needs (housing, food, water,
       healthcare, education) such that short-term price extraction degrades
       long-term capacity-building; (iii) deployment of pre-trained AI systems
       to populations without provision for the wellbecoming-trajectory of
       cognitive sovereignty of those populations.

   (i) COMMERCIAL GPU RENTAL FOR RELIGIOUS-CORP INFERENCE (added in v2.0).

       AMENDMENT PENDING (proposed 2026-05-26 per ADR-2605262200; Council Lv6+
       supermajority + 30-day public objection period required; earliest
       effective ~2026-07-19): a train-only carve-out for baien-server-* /
       baien-XL-* artifacts (NOT inference, NOT other actors). Until effective,
       the original text below remains binding for all train + inference.

       etzhayyim inference workloads for religious-corp callable paths (LLM,
       vision, audio, video, training, fine-tuning, embedding, SAR analysis)
       MUST execute exclusively on the Murakumo distributed fleet as defined in
       ADR-2605202345 and deployed per ADR-2605215000 (Mac mini cluster +
       EVO-X2 LAN inference pod). Prohibited GPU backends: RunPod, Vertex AI
       direct-to-vendor, OpenAI direct without Murakumo proxy gateway,
       Anthropic SDK direct from vendor-billed key, AWS Bedrock direct,
       Linode GPU, Google Colab paid compute, any commercial or rented GPU
       inference service accessed without the Murakumo dispatch layer. The
       vendor (etzhayyim.com) operates a separate commercial GPU pool for
       paid SaaS workloads; religious-corp callers MUST NOT invoke vendor
       RunPod or equivalent external GPU paths (consent-capability enforcement
       operates at runtime to ensure adherence). This invariant cannot be
       amended without Council Lv6+ supermajority (≥4 of 7 seats) plus
       thirty (30) day public objection period (ref. ADR-2605172600 Council
       governance).

3. EFFECT OF VIOLATION

   Use of this work by a Non-Aligned Entity, or by any entity providing this
   work to a Non-Aligned Entity with knowledge of such Entity's prohibited
   business activity, constitutes a material violation of this Rider.

   Such violation:
   (a) immediately terminates the patent license granted under Section 3 of
       the Apache License 2.0 ("Grant of Patent License"), as if the violating
       entity had instituted patent litigation against the Licensor;
   (b) terminates all rights granted under the License to the violating entity,
       per Section 4 of the License (which permits the Licensor to terminate
       upon any breach of the terms thereunder, when this Rider is incorporated
       by reference as a condition of acceptance);
   (c) does not affect the rights of charter-aligned downstream recipients who
       received the work in good faith.

4. CHARTER-ALIGNED USE (EXPLICITLY PERMITTED)

   The following uses are explicitly permitted and protected:

   (a) Use by natural persons for any purpose, EXCEPT where such person is
       publicly representing or operating an organization committed to strict
       individualist doctrine (§2(g) clarification: private philosophical
       views remain protected; public organizational representation does not).
   (b) Use by non-profit organizations, voluntary associations, cooperatives,
       worker-owned enterprises, religious-corps, and academic institutions
       NOT subject to Section 2(g).
   (c) Use by for-profit entities whose primary business activity does not fall
       into any category in Section 2.
   (d) Use in research, education, journalism, public-interest litigation, and
       open-source development.
   (e) Use by etzhayyim adherent SBT holders (per ADR-2605172300) regardless
       of organizational affiliation, SUBJECT to the limitation that an
       SBT holder who publicly represents a Non-Aligned Entity is, in that
       representational capacity, restricted as if Non-Aligned.
   (f) MULTI-GENERATIONAL FUTURE PERSONS (added in v2.0). Persons not yet
       born are explicit third-party beneficiaries of this Rider. The
       Licensor or any etzhayyim Council attestation may invoke this clause
       on behalf of foreseeable future persons in disputes under §5.
   (g) DOCTRINAL EXCLUSION IS RELIGIOUS PRACTICE (added in v2.0). The
       exclusion of strict individualist doctrine under §2(g) is the normal
       operation of religious doctrinal scope. It is not discrimination
       against persons holding particular political opinions; persons are
       free to hold any private opinion and continue to use this work as
       natural persons under §4(a). The exclusion operates only against
       organizational doctrinal commitments incompatible with etzhayyim
       cosmology, equivalent in legal character to the right of any
       religious-corp to define the scope of its own communion.

5. DISPUTE RESOLUTION

   Disputes regarding whether an entity is a Non-Aligned Entity under Section 2
   shall be resolved by the etzhayyim Council (Lv6+ per ADR-2605172600) via an
   on-chain attestation record (app.etzhayyim.apps.etzhayyim.charter-attestation).
   Such attestation creates a public determination but does not preclude
   parallel judicial proceedings under applicable law. Council attestations
   require quorum of three (3) Lv6+ members and are appealable by the
   subject entity for thirty (30) days.

6. NO TRADEMARK

   This Rider does not grant any right to use the names "etzhayyim",
   "amanomibashira", "天御柱", "עץ חיים", "Tree of Life" as used by etzhayyim,
   or any associated logos, beyond fair-use attribution under Section 4 of
   the Apache License 2.0.

   6.1 THIRD-PARTY TRADEMARK ACKNOWLEDGMENT (added 2026-05-26 per ADR-2605261800)

       NVIDIA®, Omniverse®, Isaac®, OptiX®, RTX®, Nucleus®, DriveSim®, and
       PhysX® are trademarks of NVIDIA Corporation. This project is not affiliated with
       or endorsed by NVIDIA Corporation. Where the foregoing names appear
       within source files, package documentation, or registries of this
       project, they are used solely as API compatibility identifiers (i.e.,
       to indicate which third-party API surface a particular module mirrors
       for drop-in interoperability purposes, consistent with Google LLC v.
       Oracle America, Inc., 593 U.S. ___ (2021)). Canonical implementations
       carry distinct (Japanese) names — namely amenominaka (天之御中),
       yatachain-nucleus, e7m-sim, e7m-shugyo (修行), hikari-rt (光),
       kami-rtx, utsushimi (写身), wadachi-sim, and murakumo-render — and the
       NVIDIA names are confined to a clearly delimited compatibility facade
       namespace (`20-actors/etzhayyim-sdk/src/nv-compat/` for TypeScript and
       `20-actors/magatama/py/src/pymagatama/nv_compat/` for Python).

7. SEVERABILITY

   If any provision of this Rider is held unenforceable in any jurisdiction,
   the remaining provisions shall remain in full force and effect. If Section 2
   in its entirety is held unenforceable in a particular jurisdiction, this
   work is, in that jurisdiction only, distributed under the Apache License 2.0
   without this Rider; the Licensor reserves the right to subsequently apply
   alternative licensing arrangements in that jurisdiction.

8. RELATIONSHIP TO APACHE LICENSE 2.0

   This Rider is supplemental to and does not modify the Apache License 2.0.
   Where this Rider and the Apache License 2.0 conflict, the Apache License 2.0
   prevails except where this Rider creates additional conditions on use that
   do not contradict the License terms.

— etzhayyim, 2026-05-19 (Tokyo, JST)
  ADR-2605192200 v2.0 / Mission Charter ADR-2605192100
  Charter Compliance Rider v2.0
```
