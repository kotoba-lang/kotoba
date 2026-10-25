# ISIC Coverage (generated)

**Generated from `resources/kotoba/industry/registry.edn` by `kbb --backend sci scripts/gen-industry-docs.cljk`. Do not hand-edit -- rerun the script after the registry changes.**

## Summary

| tier | count |
|---|---|
| `:implemented` | 347 |
| `:blueprint` | 25 |
| `:spec` | 276 |
| total | 648 |

Of the `:spec` entries, 146 are legacy ISIC group-level (3-digit) placeholders explicitly cross-referenced to a real, more specific `:implemented` ISIC Rev.4 class entry via `:superseded-by`. Separately, 19 legacy group ids that were themselves directly `:implemented` (own repo/business-id, left untouched) carry an optional `:superseded-code` cross-reference to a same-industry Rev.4 class sibling -- see "Superseded legacy entries" below. The remaining 130 `:spec` entries have no implemented successor yet: they are genuinely unimplemented, not stale duplicates.

## All implemented entries (347)

| ISIC | Business | business-id |
|---|---|---|
| 0111 | Growing of cereals | cloud-itonami-isic-0111 |
| 0112 | Growing of rice | cloud-itonami-isic-0112 |
| 0113 | Growing of vegetables and melons, roots and tubers | cloud-itonami-isic-0113 |
| 0114 | Growing of sugar cane | cloud-itonami-isic-0114 |
| 0115 | Growing of tobacco | cloud-itonami-isic-0115 |
| 0116 | Growing of fibre crops | cloud-itonami-isic-0116 |
| 0119 | Growing of other non-perennial crops | cloud-itonami-isic-0119 |
| 0121 | Growing of grapes | cloud-itonami-isic-0121 |
| 0122 | Growing of tropical and subtropical fruits | cloud-itonami-isic-0122 |
| 0123 | Growing of citrus fruits | cloud-itonami-isic-0123 |
| 0124 | Growing of pome fruits and stone fruits | cloud-itonami-isic-0124 |
| 0125 | Growing of other tree and bush fruits and nuts | cloud-itonami-isic-0125 |
| 0126 | Growing of oleaginous fruits | cloud-itonami-isic-0126 |
| 0127 | Growing of beverage crops | cloud-itonami-isic-0127 |
| 0130 | Plant propagation | cloud-itonami-isic-0130 |
| 0141 | Raising of cattle and buffaloes | cloud-itonami-isic-0141 |
| 0142 | Raising of horses and other equines | cloud-itonami-isic-0142 |
| 0143 | Raising of camels and camelids | cloud-itonami-isic-0143 |
| 0145 | Raising of swine/pigs | cloud-itonami-isic-0145 |
| 0146 | Raising of poultry | cloud-itonami-isic-0146 |
| 0149 | Raising of other animals | cloud-itonami-isic-0149 |
| 0150 | Mixed farming | cloud-itonami-isic-0150 |
| 0161 | Support activities for crop production | cloud-itonami-isic-0161 |
| 0162 | Community Agronomy Support | cloud-itonami-0162 |
| 0163 | Post-harvest crop activities | cloud-itonami-isic-0163 |
| 0164 | Seed processing for propagation | cloud-itonami-isic-0164 |
| 0210 | Silviculture and other forestry activities | cloud-itonami-isic-0210 |
| 0220 | Logging | cloud-itonami-isic-0220 |
| 0230 | Gathering of non-wood forest products | cloud-itonami-isic-0230 |
| 0311 | Marine fishing | cloud-itonami-0311 |
| 0312 | Freshwater fishing | cloud-itonami-isic-0312 |
| 0321 | Marine aquaculture | cloud-itonami-isic-0321 |
| 0322 | Freshwater aquaculture | cloud-itonami-isic-0322 |
| 0510 | Mining of hard coal | cloud-itonami-isic-0510 |
| 0520 | Mining of lignite | cloud-itonami-isic-0520 |
| 0610 | Extraction of crude petroleum | cloud-itonami-isic-0610 |
| 0620 | Extraction of natural gas | cloud-itonami-isic-0620 |
| 0710 | Mining of iron ores | cloud-itonami-0710 |
| 0721 | Mining of uranium and thorium ores | cloud-itonami-isic-0721 |
| 0729 | Mining of other non-ferrous metal ores | cloud-itonami-0729 |
| 0810 | Community Quarry and Stone Supply | cloud-itonami-0810 |
| 0891 | Mining of chemical and fertilizer minerals | cloud-itonami-isic-0891 |
| 0892 | Extraction of peat | cloud-itonami-isic-0892 |
| 0893 | Extraction of salt | cloud-itonami-isic-0893 |
| 0910 | Support activities for petroleum and natural gas extraction | cloud-itonami-isic-0910 |
| 0990 | Support activities for other mining and quarrying | cloud-itonami-isic-0990 |
| 1010 | Processing and preserving of meat | cloud-itonami-isic-1010 |
| 1020 | Processing and preserving of fish, crustaceans and molluscs | cloud-itonami-isic-1020 |
| 1030 | Processing and preserving of fruit and vegetables | cloud-itonami-isic-1030 |
| 1040 | Manufacture of vegetable and animal oils and fats | cloud-itonami-isic-1040 |
| 1050 | Manufacture of dairy products | cloud-itonami-isic-1050 |
| 1061 | Manufacture of grain mill products | cloud-itonami-isic-1061 |
| 1062 | Manufacture of starches and starch products | cloud-itonami-isic-1062 |
| 1071 | Manufacture of bakery products | cloud-itonami-isic-1071 |
| 1072 | Manufacture of sugar | cloud-itonami-isic-1072 |
| 1073 | Manufacture of cocoa, chocolate and sugar confectionery | cloud-itonami-isic-1073 |
| 1074 | Manufacture of macaroni, noodles, couscous and similar fari... | cloud-itonami-isic-1074 |
| 1075 | Manufacture of prepared meals and dishes | cloud-itonami-isic-1075 |
| 1079 | Manufacture of other food products n.e.c. | cloud-itonami-isic-1079 |
| 1080 | Manufacture of prepared animal feeds | cloud-itonami-isic-1080 |
| 1101 | Distilling, rectifying and blending of spirits | cloud-itonami-isic-1101 |
| 1102 | Manufacture of wines | cloud-itonami-isic-1102 |
| 1103 | Manufacture of malt liquors and malt | cloud-itonami-isic-1103 |
| 1104 | Manufacture of soft drinks | cloud-itonami-isic-1104 |
| 1200 | Manufacture of tobacco products | cloud-itonami-isic-1200 |
| 1311 | Preparation and spinning of textile fibres | cloud-itonami-isic-1311 |
| 1312 | Weaving of textiles | cloud-itonami-isic-1312 |
| 1391 | Manufacture of knitted and crocheted fabrics | cloud-itonami-isic-1391 |
| 1394 | Manufacture of cordage, rope, twine and netting | cloud-itonami-isic-1394 |
| 1410 | Manufacture of wearing apparel, except fur apparel | cloud-itonami-isic-1410 |
| 1511 | Tanning and dressing of leather | cloud-itonami-isic-1511 |
| 1520 | Manufacture of footwear | cloud-itonami-isic-1520 |
| 1610 | Sawmilling and planing of wood | cloud-itonami-isic-1610 |
| 1621 | Manufacture of veneer sheets and wood-based panels | cloud-itonami-isic-1621 |
| 1622 | Manufacture of builders' carpentry and joinery | cloud-itonami-isic-1622 |
| 1623 | Manufacture of wooden containers | cloud-itonami-isic-1623 |
| 1629 | Manufacture of other products of wood | cloud-itonami-isic-1629 |
| 1701 | Manufacture of pulp, paper and paperboard | cloud-itonami-isic-1701 |
| 1702 | Manufacture of corrugated paper and paperboard and of containers of paper and paperboard | cloud-itonami-isic-1702 |
| 1709 | Manufacture of other articles of paper and paperboard | cloud-itonami-isic-1709 |
| 1811 | Printing | cloud-itonami-1811 |
| 1812 | Service activities related to printing | cloud-itonami-1812 |
| 1820 | Reproduction of recorded media | cloud-itonami-isic-1820 |
| 1910 | Manufacture of coke oven products | cloud-itonami-isic-1910 |
| 1920 | Manufacture of refined petroleum products | cloud-itonami-isic-1920 |
| 2011 | Manufacture of basic chemicals | cloud-itonami-2011 |
| 2012 | Manufacture of fertilizers and nitrogen compounds | cloud-itonami-isic-2012 |
| 2013 | Manufacture of plastics and synthetic rubber in primary forms | cloud-itonami-isic-2013 |
| 2021 | Manufacture of pesticides and other agrochemical products | cloud-itonami-isic-2021 |
| 2022 | Manufacture of paints, varnishes and similar coatings, prin... | cloud-itonami-isic-2022 |
| 2023 | Manufacture of soap and detergents, cleaning and polishing ... | cloud-itonami-isic-2023 |
| 2030 | Manufacture of man-made fibres | cloud-itonami-isic-2030 |
| 2100 | Manufacture of pharmaceuticals, medicinal chemical and bota... | cloud-itonami-isic-2100 |
| 2211 | Manufacture of rubber tyres and tubes | cloud-itonami-isic-2211 |
| 2219 | Manufacture of other rubber products | cloud-itonami-isic-2219 |
| 2220 | Manufacture of plastics products | cloud-itonami-isic-2220 |
| 2310 | Manufacture of glass and glass products | cloud-itonami-isic-2310 |
| 2392 | Manufacture of clay building materials | cloud-itonami-isic-2392 |
| 2394 | Manufacture of cement, lime and plaster | cloud-itonami-isic-2394 |
| 2395 | Manufacture of articles of concrete, cement and plaster | cloud-itonami-isic-2395 |
| 2410 | Manufacture of Basic Iron and Steel | cloud-itonami-isic-2410 |
| 2420 | Manufacture of basic precious and other non-ferrous metals | cloud-itonami-isic-2420 |
| 2431 | Casting of iron and steel | cloud-itonami-isic-2431 |
| 2432 | Casting of non-ferrous metals | cloud-itonami-isic-2432 |
| 2511 | Manufacture of structural metal products | cloud-itonami-isic-2511 |
| 2512 | Manufacture of tanks, reservoirs and containers of metal | cloud-itonami-isic-2512 |
| 2591 | Forging, pressing, stamping and roll-forming of metal | cloud-itonami-isic-2591 |
| 2592 | Treatment and coating of metals | cloud-itonami-isic-2592 |
| 2593 | Manufacture of cutlery, hand tools and general hardware | cloud-itonami-isic-2593 |
| 2599 | Manufacture of other fabricated metal products n.e.c. | cloud-itonami-isic-2599 |
| 2610 | Semiconductor and Electronics Manufacturing Enablement | cloud-itonami-isic-2610 |
| 2620 | Manufacture of computers and peripheral equipment | cloud-itonami-isic-2620 |
| 2630 | Manufacture of communication equipment | cloud-itonami-isic-2630 |
| 2640 | Manufacture of consumer electronics | cloud-itonami-isic-2640 |
| 2651 | Manufacture of measuring, testing, navigating and control e... | cloud-itonami-isic-2651 |
| 2652 | Manufacture of watches and clocks | cloud-itonami-2652 |
| 2660 | Manufacture of irradiation, electromedical and electrothera... | cloud-itonami-2660 |
| 2670 | Manufacture of optical instruments and photographic equipment | cloud-itonami-isic-2670 |
| 2680 | Manufacture of magnetic and optical media | cloud-itonami-isic-2680 |
| 2710 | Manufacture of electric motors, generators, transformers an... | cloud-itonami-isic-2710 |
| 2720 | Manufacture of batteries and accumulators | cloud-itonami-isic-2720 |
| 2731 | Manufacture of fibre optic cables | cloud-itonami-isic-2731 |
| 2732 | Manufacture of other electronic and electric wires and cables | cloud-itonami-isic-2732 |
| 2733 | Manufacture of wiring devices | cloud-itonami-isic-2733 |
| 2740 | Manufacture of electric lighting equipment | cloud-itonami-isic-2740 |
| 2750 | Manufacture of domestic appliances | cloud-itonami-isic-2750 |
| 2790 | Manufacture of other electrical equipment | cloud-itonami-isic-2790 |
| 2811 | Manufacture of Engines and Turbines | cloud-itonami-isic-2811 |
| 2812 | Manufacture of fluid power equipment | cloud-itonami-isic-2812 |
| 2813 | Manufacture of other pumps, compressors, taps and valves | cloud-itonami-isic-2813 |
| 2814 | Manufacture of bearings, gears, gearing and driving elements | cloud-itonami-isic-2814 |
| 2816 | Manufacture of lifting and handling equipment | cloud-itonami-isic-2816 |
| 2817 | Manufacture of office machinery and equipment (except computers and peripheral equipment) | cloud-itonami-isic-2817 |
| 2818 | Manufacture of power-driven hand tools | cloud-itonami-isic-2818 |
| 2819 | Manufacture of other general-purpose machinery | cloud-itonami-isic-2819 |
| 2821 | Manufacture of agricultural and forestry machinery | cloud-itonami-isic-2821 |
| 2822 | Manufacture of metal-forming machinery and machine tools | cloud-itonami-isic-2822 |
| 2824 | Manufacture of machinery for mining, quarrying and construction | cloud-itonami-isic-2824 |
| 2825 | Manufacture of machinery for food, beverage and tobacco pro... | cloud-itonami-isic-2825 |
| 2826 | Manufacture of machinery for textile, apparel and leather p... | cloud-itonami-isic-2826 |
| 2910 | Manufacture of motor vehicles | cloud-itonami-isic-2910 |
| 2920 | Manufacture of bodies (coachwork) for motor vehicles | cloud-itonami-isic-2920 |
| 2930 | Manufacture of parts and accessories for motor vehicles | cloud-itonami-isic-2930 |
| 3011 | Building of Ships and Floating Structures | cloud-itonami-isic-3011 |
| 3012 | Building of pleasure and sporting boats | cloud-itonami-isic-3012 |
| 3020 | Manufacture of railway locomotives and rolling stock | cloud-itonami-3020 |
| 3030 | Aircraft and Aerospace Manufacturing Enablement | cloud-itonami-isic-3030 |
| 3091 | Manufacture of motorcycles | cloud-itonami-isic-3091 |
| 3092 | Manufacture of bicycles and invalid carriages | cloud-itonami-isic-3092 |
| 3099 | Manufacture of other transport equipment n.e.c. | cloud-itonami-isic-3099 |
| 3100 | Manufacture of furniture | cloud-itonami-isic-3100 |
| 3211 | Manufacture of jewellery and related articles | cloud-itonami-isic-3211 |
| 3212 | Manufacture of imitation jewellery and related articles | cloud-itonami-isic-3212 |
| 3220 | Manufacture of musical instruments | cloud-itonami-isic-3220 |
| 3230 | Manufacture of sports goods | cloud-itonami-isic-3230 |
| 3240 | Manufacture of games and toys | cloud-itonami-isic-3240 |
| 3250 | Manufacture of medical and dental instruments and supplies | cloud-itonami-isic-3250 |
| 3311 | Repair of fabricated metal products | cloud-itonami-isic-3311 |
| 3312 | Repair of machinery | cloud-itonami-3312 |
| 3313 | Repair of electronic and optical equipment | cloud-itonami-3313 |
| 3314 | Repair of electrical equipment | cloud-itonami-isic-3314 |
| 3319 | Repair of other equipment | cloud-itonami-isic-3319 |
| 3320 | Installation of industrial machinery and equipment | cloud-itonami-isic-3320 |
| 3510 | Electric power generation, transmission and distribution | cloud-itonami-3510 |
| 3512 | Community Renewable Energy Operations | cloud-itonami-isic-3512 |
| 3520 | Manufacture of gas | cloud-itonami-isic-3520 |
| 3530 | Steam and air conditioning supply | cloud-itonami-isic-3530 |
| 3600 | Community Water Safety Operations | cloud-itonami-isic-3600 |
| 3700 | Sewerage | cloud-itonami-isic-3700 |
| 3811 | Collection of non-hazardous waste | cloud-itonami-isic-3811 |
| 3812 | Collection of hazardous waste | cloud-itonami-3812 |
| 3821 | Treatment and disposal of non-hazardous waste | cloud-itonami-isic-3821 |
| 3822 | Treatment and disposal of hazardous waste | cloud-itonami-isic-3822 |
| 3830 | Local Materials Recovery | cloud-itonami-isic-3830 |
| 3900 | Remediation activities and other waste management services | cloud-itonami-isic-3900 |
| 4100 | Construction of buildings | cloud-itonami-isic-4100 |
| 4210 | Construction of roads and railways | cloud-itonami-isic-4210 |
| 4211 | Community Building Construction | cloud-itonami-4211 |
| 4220 | Construction of utility projects | cloud-itonami-isic-4220 |
| 4311 | Demolition | cloud-itonami-isic-4311 |
| 4312 | Site preparation | cloud-itonami-isic-4312 |
| 4321 | Electrical installation | cloud-itonami-4321 |
| 4322 | Plumbing, heat and air-conditioning installation | cloud-itonami-4322 |
| 4329 | Other construction installation | cloud-itonami-isic-4329 |
| 4330 | Building completion and finishing | cloud-itonami-isic-4330 |
| 4390 | Other specialized construction activities | cloud-itonami-isic-4390 |
| 4510 | Sale of motor vehicles | cloud-itonami-isic-4510 |
| 4610 | Wholesale on a fee or contract basis | cloud-itonami-isic-4610 |
| 4620 | Wholesale of agricultural raw materials and live animals | cloud-itonami-isic-4620 |
| 4630 | Wholesale of food, beverages and tobacco | cloud-itonami-isic-4630 |
| 4641 | Wholesale of textiles, clothing and footwear | cloud-itonami-isic-4641 |
| 4649 | Wholesale of other household goods | cloud-itonami-isic-4649 |
| 4651 | Wholesale of computers, computer peripheral equipment and s... | cloud-itonami-isic-4651 |
| 4652 | Wholesale of electronic and telecommunications equipment an... | cloud-itonami-isic-4652 |
| 4653 | Wholesale of agricultural machinery, equipment and supplies | cloud-itonami-isic-4653 |
| 4659 | Wholesale of other machinery and equipment | cloud-itonami-isic-4659 |
| 4662 | Wholesale of metals and metal ores | cloud-itonami-isic-4662 |
| 4663 | Wholesale of construction materials, hardware, plumbing and... | cloud-itonami-isic-4663 |
| 4669 | Wholesale of waste and scrap and other products n.e.c. | cloud-itonami-isic-4669 |
| 4671 | Wholesale of solid, liquid and gaseous fuels and related products | cloud-itonami-isic-4671 |
| 4690 | Non-specialized wholesale trade | cloud-itonami-isic-4690 |
| 4711 | Community Retail Operations | cloud-itonami-4711 |
| 4730 | Retail sale of automotive fuel in specialized stores | cloud-itonami-isic-4730 |
| 4741 | Retail sale of computers, peripheral equipment and software in specialized stores | cloud-itonami-isic-4741 |
| 4772 | Retail sale of pharmaceutical and medical goods, cosmetic a... | cloud-itonami-isic-4772 |
| 4774 | Retail sale of second-hand goods | cloud-itonami-isic-4774 |
| 4920 | Community Freight Transport | cloud-itonami-4920 |
| 4950 | Transport via pipeline (petroleum) | cloud-itonami-isic-4950 |
| 5020 | Water freight transport (petroleum tanker) | cloud-itonami-isic-5020 |
| 5210 | Warehousing and storage | cloud-itonami-isic-5210 |
| 5320 | Courier activities | cloud-itonami-isic-5320 |
| 5510 | Community Accommodation Operations | cloud-itonami-5510 |
| 5590 | Other accommodation | cloud-itonami-isic-5590 |
| 561 | Restaurants and mobile food service activities | cloud-itonami-isic-561 |
| 562 | Event catering and other food service activities | cloud-itonami-isic-562 |
| 563 | Beverage serving activities | cloud-itonami-isic-563 |
| 5820 | Software publishing | cloud-itonami-isic-5820 |
| 6110 | Wired telecommunications activities | cloud-itonami-isic-6110 |
| 6120 | Wireless telecommunications activities | cloud-itonami-6120 |
| 6130 | Satellite telecommunications activities | cloud-itonami-isic-6130 |
| 6190 | Community Telecommunications Access | cloud-itonami-isic-6190 |
| 6201 | Computer programming activities | cloud-itonami-isic-6201 |
| 6202 | Computer consultancy and computer facilities management act... | cloud-itonami-isic-6202 |
| 6209 | Other information technology and computer service activities | cloud-itonami-isic-6209 |
| 6310 | Talent Actor | cloud-itonami-isic-6310 |
| 6311 | Data processing, hosting and related activities | cloud-itonami-isic-6311 |
| 6312 | Web portals | cloud-itonami-isic-6312 |
| 6391 | News agency activities | cloud-itonami-isic-6391 |
| 6399 | Meta Job Search | cloud-itonami-isic-6399 |
| 6411 | Central banking | cloud-itonami-isic-6411 |
| 6419 | Community Monetary Intermediation | cloud-itonami-isic-6419 |
| 6420 | Activities of holding companies | cloud-itonami-isic-6420 |
| 6430 | Trusts, funds and similar financial entities | cloud-itonami-isic-6430 |
| 6491 | Financial leasing | cloud-itonami-isic-6491 |
| 6492 | Other credit granting | cloud-itonami-isic-6492 |
| 6493 | Factoring activities | cloud-itonami-isic-6493 |
| 6499 | Other financial service activities, except insurance and pe... | cloud-itonami-isic-6499 |
| 6511 | Life insurance | cloud-itonami-isic-6511 |
| 6512 | Non-life insurance | cloud-itonami-isic-6512 |
| 6520 | Reinsurance | cloud-itonami-isic-6520 |
| 6530 | Pension funding | cloud-itonami-isic-6530 |
| 6611 | Administration of financial markets | cloud-itonami-isic-6611 |
| 6612 | Security and commodity contracts brokerage | cloud-itonami-isic-6612 |
| 6619 | Card Transaction Processing and Settlement | cloud-itonami-isic-6619 |
| 6621 | Risk and damage evaluation | cloud-itonami-isic-6621 |
| 6622 | Activities of insurance agents and brokers | cloud-itonami-isic-6622 |
| 6629 | Other activities auxiliary to insurance and pension funding | cloud-itonami-isic-6629 |
| 6630 | Fund management activities | cloud-itonami-isic-6630 |
| 6810 | Community Real-Estate Agency | cloud-itonami-isic-6810 |
| 6820 | Real estate activities on a fee or contract basis | cloud-itonami-isic-6820 |
| 6910 | Legal activities | cloud-itonami-isic-6910 |
| 6920 | Accounting, bookkeeping and auditing activities | cloud-itonami-isic-6920 |
| 7010 | Activities of head offices | cloud-itonami-isic-7010 |
| 7020 | Management consultancy activities | cloud-itonami-isic-7020 |
| 7110 | Community Architectural and Engineering Practice | cloud-itonami-7110 |
| 7120 | Technical testing and analysis | cloud-itonami-isic-7120 |
| 7210 | Research and experimental development on natural sciences a... | cloud-itonami-isic-7210 |
| 7220 | Research and experimental development on social sciences an... | cloud-itonami-isic-7220 |
| 7310 | Advertising | cloud-itonami-isic-7310 |
| 7320 | Market research and public opinion polling | cloud-itonami-isic-7320 |
| 7410 | Specialized design activities | cloud-itonami-isic-7410 |
| 7420 | Photographic activities | cloud-itonami-isic-7420 |
| 7490 | Other professional, scientific and technical activities n.e.c. | cloud-itonami-isic-7490 |
| 750 | Veterinary activities | cloud-itonami-isic-750 |
| 7500 | Veterinary activities | cloud-itonami-isic-7500 |
| 7810 | Community Employment Agency | cloud-itonami-7810 |
| 7820 | Temporary employment agency activities | cloud-itonami-isic-7820 |
| 7830 | Other human resources provision | cloud-itonami-isic-7830 |
| 8291 | Corporate/Compliance Intelligence Actor | cloud-itonami-isic-8291 |
| 8299 | Other business support service activities n.e.c. | cloud-itonami-isic-8299 |
| 8411 | Community Public Administration Service | cloud-itonami-8411 |
| 8412 | Health Care, Education, Cultural Services, Social Services Regulatory Administration | cloud-itonami-isic-8412 |
| 8413 | Economic regulation and business compliance administration | cloud-itonami-isic-8413 |
| 8421 | Foreign affairs and consular services administration | cloud-itonami-isic-8421 |
| 8422 | Defence procurement and logistics administration | cloud-itonami-isic-8422 |
| 8423 | Public order and safety administrative operations | cloud-itonami-isic-8423 |
| 8430 | Compulsory social security activities | cloud-itonami-isic-8430 |
| 851 | Pre-primary and primary education | cloud-itonami-isic-851 |
| 8510 | Pre-primary and primary education | cloud-itonami-isic-8510 |
| 852 | Secondary education | cloud-itonami-isic-852 |
| 8521 | General secondary education | cloud-itonami-isic-8521 |
| 8522 | Technical and vocational secondary education | cloud-itonami-isic-8522 |
| 853 | Higher education | cloud-itonami-isic-853 |
| 8530 | Higher education | cloud-itonami-isic-8530 |
| 854 | Other education | cloud-itonami-isic-854 |
| 8541 | Sports and recreation education | cloud-itonami-isic-8541 |
| 8542 | Cultural education | cloud-itonami-isic-8542 |
| 8549 | Other education n.e.c. | cloud-itonami-isic-8549 |
| 855 | Educational support activities | cloud-itonami-isic-855 |
| 8550 | Educational support activities | cloud-itonami-isic-8550 |
| 8569 | Community Learning Support | cloud-itonami-isic-8569 |
| 861 | Hospital activities | cloud-itonami-isic-861 |
| 8610 | Hospital activities | cloud-itonami-isic-8610 |
| 862 | Medical and dental practice activities | cloud-itonami-isic-862 |
| 8620 | Medical and dental practice activities | cloud-itonami-isic-8620 |
| 869 | Other human health activities | cloud-itonami-isic-869 |
| 8690 | Other human health activities | cloud-itonami-isic-8690 |
| 8691 | Health Access Navigation | cloud-itonami-isic-8691 |
| 871 | Residential nursing care facilities | cloud-itonami-isic-871 |
| 8710 | Residential nursing care facilities | cloud-itonami-isic-8710 |
| 872 | Residential care activities for mental retardation, menta... | cloud-itonami-isic-872 |
| 8720 | Residential care activities for mental retardation, mental ... | cloud-itonami-isic-8720 |
| 873 | Residential care activities for the elderly and disabled | cloud-itonami-isic-873 |
| 8730 | Residential care activities for the elderly and disabled | cloud-itonami-isic-8730 |
| 879 | Other residential care activities | cloud-itonami-isic-879 |
| 8790 | Other residential care activities | cloud-itonami-isic-8790 |
| 8810 | Community Care Coordination | cloud-itonami-isic-8810 |
| 889 | Other social work activities without accommodation | cloud-itonami-isic-889 |
| 8890 | Other social work activities without accommodation | cloud-itonami-isic-8890 |
| 900 | Creative, arts and entertainment activities | cloud-itonami-isic-900 |
| 9000 | Creative, arts and entertainment activities | cloud-itonami-isic-9000 |
| 9101 | Community Library and Archive | cloud-itonami-9101 |
| 9102 | Museums activities and operation of historical sites and bu... | cloud-itonami-isic-9102 |
| 9103 | Botanical and zoological gardens and nature reserves activi... | cloud-itonami-isic-9103 |
| 920 | Gambling and betting activities | cloud-itonami-isic-920 |
| 9200 | Gambling and betting activities | cloud-itonami-isic-9200 |
| 931 | Sports activities | cloud-itonami-isic-931 |
| 9311 | Operation of sports facilities | cloud-itonami-isic-9311 |
| 9312 | Activities of sports clubs | cloud-itonami-isic-9312 |
| 9319 | Other sports activities | cloud-itonami-isic-9319 |
| 932 | Other amusement and recreation activities | cloud-itonami-isic-932 |
| 9321 | Activities of amusement parks and theme parks | cloud-itonami-isic-9321 |
| 9329 | Other amusement and recreation activities n.e.c. | cloud-itonami-isic-9329 |
| 941 | Activities of business, employers and professional membership organizations | cloud-itonami-isic-941 |
| 9411 | Activities of business and employers membership organizations | cloud-itonami-isic-9411 |
| 9412 | Activities of professional membership organizations | cloud-itonami-isic-9412 |
| 942 | Activities of trade unions | cloud-itonami-isic-942 |
| 9420 | Activities of trade unions | cloud-itonami-isic-9420 |
| 949 | Activities of other membership organizations | cloud-itonami-isic-949 |
| 9491 | Activities of religious organizations | cloud-itonami-isic-9491 |
| 9492 | Activities of political organizations | cloud-itonami-isic-9492 |
| 9499 | Activities of other membership organizations n.e.c. | cloud-itonami-isic-9499 |
| 9511 | Community ICT Equipment Repair | cloud-itonami-9511 |
| 9512 | Repair of communication equipment | cloud-itonami-isic-9512 |
| 952 | Repair of personal and household goods | cloud-itonami-isic-952 |
| 9521 | Repair of consumer electronics | cloud-itonami-isic-9521 |
| 9522 | Repair of household appliances and home and garden equipment | cloud-itonami-isic-9522 |
| 9523 | Repair of footwear and leather goods | cloud-itonami-isic-9523 |
| 9524 | Repair of furniture and home furnishings | cloud-itonami-isic-9524 |
| 9529 | Repair of other personal and household goods | cloud-itonami-isic-9529 |
| 960 | Other personal service activities | cloud-itonami-isic-960 |
| 9601 | Washing and | cloud-itonami-isic-9601 |
| 9602 | Hairdressing and other beauty treatment | cloud-itonami-isic-9602 |
| 9603 | Funeral and related activities | cloud-itonami-isic-9603 |
| 9609 | Other personal service activities n.e.c. | cloud-itonami-isic-9609 |
| 9700 | Community Domestic Employment | cloud-itonami-9700 |
| 9900 | Community Mission Operations Support | cloud-itonami-9900 |

## Superseded legacy entries (165)

Legacy ISIC group-level (3-digit) registry entries superseded by a more specific, real ISIC Rev.4 class-level entry. `:superseded-by` marks a `:spec` placeholder pointing at its real `:implemented` successor(s); `:superseded-code` marks a legacy entry that was *itself* directly implemented (own repo/business-id, left untouched) but has a same-industry Rev.4 class sibling worth knowing about.

| ISIC (legacy) | Name | successor(s) | legacy entry's own maturity |
|---|---|---|---|
| 011 | Growing of non-perennial crops | 0111, 0112, 0113, 0114, 0115, 0116, 0119 | spec (placeholder) |
| 012 | Growing of perennial crops | 0121, 0122, 0123, 0124, 0125, 0126, 0127 | spec (placeholder) |
| 013 | Plant propagation | 0130 | spec (placeholder) |
| 014 | Animal production | 0141, 0142, 0143, 0145, 0146, 0149 | spec (placeholder) |
| 015 | Mixed farming | 0150 | spec (placeholder) |
| 021 | Silviculture and other forestry activities | 0210 | spec (placeholder) |
| 022 | Logging | 0220 | spec (placeholder) |
| 023 | Gathering of non-wood forest products | 0230 | spec (placeholder) |
| 031 | Fishing | 0311, 0312 | spec (placeholder) |
| 032 | Aquaculture | 0321, 0322 | spec (placeholder) |
| 051 | Mining of hard coal | 0510 | spec (placeholder) |
| 052 | Mining of lignite | 0520 | spec (placeholder) |
| 061 | Extraction of crude petroleum | 0610 | spec (placeholder) |
| 062 | Extraction of natural gas | 0620 | spec (placeholder) |
| 071 | Mining of iron ores | 0710 | spec (placeholder) |
| 072 | Mining of non-ferrous metal ores | 0721, 0729 | spec (placeholder) |
| 089 | Mining and quarrying n.e.c. | 0891, 0892, 0893 | spec (placeholder) |
| 091 | Support activities for petroleum and natural gas extraction | 0910 | spec (placeholder) |
| 099 | Support activities for other mining and quarrying | 0990 | spec (placeholder) |
| 101 | Processing and preserving of meat | 1010 | spec (placeholder) |
| 102 | Processing and preserving of fish, crustaceans and molluscs | 1020 | spec (placeholder) |
| 103 | Processing and preserving of fruit and vegetables | 1030 | spec (placeholder) |
| 104 | Manufacture of vegetable and animal oils and fats | 1040 | spec (placeholder) |
| 105 | Manufacture of dairy products | 1050 | spec (placeholder) |
| 106 | Manufacture of grain mill products, starches and starch p... | 1061, 1062 | spec (placeholder) |
| 107 | Manufacture of other food products | 1071, 1072, 1073, 1074, 1075, 1079 | spec (placeholder) |
| 108 | Manufacture of prepared animal feeds | 1080 | spec (placeholder) |
| 110 | Manufacture of beverages | 1101, 1102, 1103, 1104 | spec (placeholder) |
| 120 | Manufacture of tobacco products | 1200 | spec (placeholder) |
| 131 | Spinning, weaving and finishing of textiles | 1311, 1312 | spec (placeholder) |
| 139 | Manufacture of other textiles | 1391, 1394 | spec (placeholder) |
| 141 | Manufacture of wearing apparel, except fur apparel | 1410 | spec (placeholder) |
| 151 | Tanning and dressing of leather | 1511 | spec (placeholder) |
| 152 | Manufacture of footwear | 1520 | spec (placeholder) |
| 161 | Sawmilling and planing of wood | 1610 | spec (placeholder) |
| 162 | Manufacture of products of wood, cork, straw and plaiting... | 1621, 1622, 1623, 1629 | spec (placeholder) |
| 170 | Manufacture of paper and paper products | 1701, 1702, 1709 | spec (placeholder) |
| 181 | Printing and service activities related to printing | 1811, 1812 | spec (placeholder) |
| 182 | Reproduction of recorded media | 1820 | spec (placeholder) |
| 191 | Manufacture of coke oven products | 1910 | spec (placeholder) |
| 192 | Manufacture of refined petroleum products | 1920 | spec (placeholder) |
| 201 | Manufacture of basic chemicals, fertilizers and nitrogen ... | 2011, 2012, 2013 | spec (placeholder) |
| 202 | Manufacture of other chemical products | 2021, 2022, 2023 | spec (placeholder) |
| 203 | Manufacture of man-made fibres | 2030 | spec (placeholder) |
| 210 | Manufacture of pharmaceuticals, medicinal chemical and bo... | 2100 | spec (placeholder) |
| 221 | Manufacture of rubber products | 2211, 2219 | spec (placeholder) |
| 222 | Manufacture of plastics products | 2220 | spec (placeholder) |
| 231 | Manufacture of glass and glass products | 2310 | spec (placeholder) |
| 239 | Manufacture of non-metallic mineral products n.e.c. | 2392, 2394, 2395 | spec (placeholder) |
| 241 | Manufacture of basic iron and steel | 2410 | spec (placeholder) |
| 242 | Manufacture of basic precious and other non-ferrous metals | 2420 | spec (placeholder) |
| 243 | Casting of metals | 2431, 2432 | spec (placeholder) |
| 251 | Manufacture of structural metal products, tanks, reservoi... | 2511, 2512 | spec (placeholder) |
| 259 | Manufacture of other fabricated metal products | 2591, 2592, 2593, 2599 | spec (placeholder) |
| 262 | Manufacture of computers and peripheral equipment | 2620 | spec (placeholder) |
| 263 | Manufacture of communication equipment | 2630 | spec (placeholder) |
| 264 | Manufacture of consumer electronics | 2640 | spec (placeholder) |
| 265 | Manufacture of measuring, testing, navigating and control... | 2651, 2652 | spec (placeholder) |
| 266 | Manufacture of irradiation, electromedical and electrothe... | 2660 | spec (placeholder) |
| 267 | Manufacture of optical instruments and photographic equip... | 2670 | spec (placeholder) |
| 268 | Manufacture of magnetic and optical media | 2680 | spec (placeholder) |
| 271 | Manufacture of electric motors, generators, transformers ... | 2710 | spec (placeholder) |
| 272 | Manufacture of batteries and accumulators | 2720 | spec (placeholder) |
| 273 | Manufacture of wiring and wiring devices | 2731, 2732, 2733 | spec (placeholder) |
| 274 | Manufacture of electric lighting equipment | 2740 | spec (placeholder) |
| 275 | Manufacture of domestic appliances | 2750 | spec (placeholder) |
| 279 | Manufacture of other electrical equipment | 2790 | spec (placeholder) |
| 281 | Manufacture of general-purpose machinery | 2811, 2812, 2813, 2814, 2816, 2817, 2818, 2819 | spec (placeholder) |
| 282 | Manufacture of special-purpose machinery | 2821, 2822, 2824, 2825, 2826 | spec (placeholder) |
| 291 | Manufacture of motor vehicles | 2910 | spec (placeholder) |
| 292 | Manufacture of bodies | 2920 | spec (placeholder) |
| 293 | Manufacture of parts and accessories for motor vehicles | 2930 | spec (placeholder) |
| 301 | Building of ships and boats | 3011, 3012 | spec (placeholder) |
| 302 | Manufacture of railway locomotives and rolling stock | 3020 | spec (placeholder) |
| 309 | Manufacture of transport equipment n.e.c. | 3091, 3092, 3099 | spec (placeholder) |
| 310 | Manufacture of furniture | 3100 | spec (placeholder) |
| 321 | Manufacture of jewellery, bijouterie and related articles | 3211, 3212 | spec (placeholder) |
| 322 | Manufacture of musical instruments | 3220 | spec (placeholder) |
| 323 | Manufacture of sports goods | 3230 | spec (placeholder) |
| 324 | Manufacture of games and toys | 3240 | spec (placeholder) |
| 325 | Manufacture of medical and dental instruments and supplies | 3250 | spec (placeholder) |
| 331 | Repair of fabricated metal products, machinery and equipment | 3311, 3312, 3313, 3314, 3319 | spec (placeholder) |
| 332 | Installation of industrial machinery and equipment | 3320 | spec (placeholder) |
| 351 | Electric power generation, transmission and distribution | 3510, 3512 | spec (placeholder) |
| 352 | Manufacture of gas | 3520 | spec (placeholder) |
| 353 | Steam and air conditioning supply | 3530 | spec (placeholder) |
| 370 | Sewerage | 3700 | spec (placeholder) |
| 381 | Waste collection | 3811, 3812 | spec (placeholder) |
| 382 | Waste treatment and disposal | 3821, 3822 | spec (placeholder) |
| 390 | Remediation activities and other waste management services | 3900 | spec (placeholder) |
| 410 | Construction of buildings | 4100 | spec (placeholder) |
| 421 | Construction of roads and railways | 4210, 4211 | spec (placeholder) |
| 422 | Construction of utility projects | 4220 | spec (placeholder) |
| 431 | Demolition and site preparation | 4311, 4312 | spec (placeholder) |
| 432 | Electrical, plumbing and other construction installation ... | 4321, 4322, 4329 | spec (placeholder) |
| 433 | Building completion and finishing | 4330 | spec (placeholder) |
| 439 | Other specialized construction activities | 4390 | spec (placeholder) |
| 451 | Sale of motor vehicles | 4510 | spec (placeholder) |
| 461 | Wholesale on a fee or contract basis | 4610 | spec (placeholder) |
| 462 | Wholesale of agricultural raw materials and live animals | 4620 | spec (placeholder) |
| 463 | Wholesale of food, beverages and tobacco | 4630 | spec (placeholder) |
| 464 | Wholesale of household goods | 4641, 4649 | spec (placeholder) |
| 465 | Wholesale of machinery, equipment and supplies | 4651, 4652, 4653, 4659 | spec (placeholder) |
| 466 | Other specialized wholesale | 4662, 4663, 4669 | spec (placeholder) |
| 469 | Non-specialized wholesale trade | 4690 | spec (placeholder) |
| 473 | Retail sale of automotive fuel in specialized stores | 4730 | spec (placeholder) |
| 474 | Retail sale of information and communications equipment i... | 4741 | spec (placeholder) |
| 477 | Retail sale of other goods in specialized stores | 4772, 4774 | spec (placeholder) |
| 492 | Other land transport | 4920 | spec (placeholder) |
| 502 | Inland water transport | 5020 | spec (placeholder) |
| 521 | Warehousing and storage | 5210 | spec (placeholder) |
| 532 | Courier activities | 5320 | spec (placeholder) |
| 559 | Other accommodation | 5590 | spec (placeholder) |
| 582 | Software publishing | 5820 | spec (placeholder) |
| 611 | Wired telecommunications activities | 6110 | spec (placeholder) |
| 612 | Wireless telecommunications activities | 6120 | spec (placeholder) |
| 613 | Satellite telecommunications activities | 6130 | spec (placeholder) |
| 620 | Computer programming, consultancy and related activities | 6201, 6202, 6209 | spec (placeholder) |
| 631 | Data processing, hosting and related activities | 6310, 6311, 6312 | spec (placeholder) |
| 639 | Other information service activities | 6391, 6399 | spec (placeholder) |
| 642 | Activities of holding companies | 6420 | spec (placeholder) |
| 643 | Trusts, funds and similar financial entities | 6430 | spec (placeholder) |
| 649 | Other financial service activities, except insurance and ... | 6491, 6492, 6493, 6499 | spec (placeholder) |
| 651 | Insurance | 6511, 6512 | spec (placeholder) |
| 652 | Reinsurance | 6520 | spec (placeholder) |
| 653 | Pension funding | 6530 | spec (placeholder) |
| 662 | Activities auxiliary to insurance and pension funding | 6621, 6622, 6629 | spec (placeholder) |
| 663 | Fund management activities | 6630 | spec (placeholder) |
| 682 | Real estate activities on a fee or contract basis | 6820 | spec (placeholder) |
| 691 | Legal activities | 6910 | spec (placeholder) |
| 692 | Accounting, bookkeeping and auditing activities | 6920 | spec (placeholder) |
| 701 | Activities of head offices | 7010 | spec (placeholder) |
| 702 | Management consultancy activities | 7020 | spec (placeholder) |
| 712 | Technical testing and analysis | 7120 | spec (placeholder) |
| 721 | Research and experimental development on natural sciences... | 7210 | spec (placeholder) |
| 722 | Research and experimental development on social sciences ... | 7220 | spec (placeholder) |
| 731 | Advertising | 7310 | spec (placeholder) |
| 732 | Market research and public opinion polling | 7320 | spec (placeholder) |
| 741 | Specialized design activities | 7410 | spec (placeholder) |
| 742 | Photographic activities | 7420 | spec (placeholder) |
| 749 | Other professional, scientific and technical activities n... | 7490 | spec (placeholder) |
| 750 | Veterinary activities | 7500 | implemented (legacy ISIC group id) |
| 782 | Temporary employment agency activities | 7820 | spec (placeholder) |
| 783 | Other human resources provision | 7830 | spec (placeholder) |
| 829 | Business support service activities n.e.c. | 8291, 8299 | spec (placeholder) |
| 842 | Provision of services to the community as a whole | 8421, 8422, 8423 | spec (placeholder) |
| 843 | Compulsory social security activities | 8430 | spec (placeholder) |
| 851 | Pre-primary and primary education | 8510 | implemented (legacy ISIC group id) |
| 853 | Higher education | 8530 | implemented (legacy ISIC group id) |
| 854 | Other education | 8549 | implemented (legacy ISIC group id) |
| 855 | Educational support activities | 8550 | implemented (legacy ISIC group id) |
| 861 | Hospital activities | 8610 | implemented (legacy ISIC group id) |
| 862 | Medical and dental practice activities | 8620 | implemented (legacy ISIC group id) |
| 869 | Other human health activities | 8690 | implemented (legacy ISIC group id) |
| 871 | Residential nursing care facilities | 8710 | implemented (legacy ISIC group id) |
| 872 | Residential care activities for mental retardation, menta... | 8720 | implemented (legacy ISIC group id) |
| 873 | Residential care activities for the elderly and disabled | 8730 | implemented (legacy ISIC group id) |
| 879 | Other residential care activities | 8790 | implemented (legacy ISIC group id) |
| 889 | Other social work activities without accommodation | 8890 | implemented (legacy ISIC group id) |
| 900 | Creative, arts and entertainment activities | 9000 | implemented (legacy ISIC group id) |
| 920 | Gambling and betting activities | 9200 | implemented (legacy ISIC group id) |
| 932 | Other amusement and recreation activities | 9329 | implemented (legacy ISIC group id) |
| 942 | Activities of trade unions | 9420 | implemented (legacy ISIC group id) |
| 949 | Activities of other membership organizations | 9499 | implemented (legacy ISIC group id) |
| 960 | Other personal service activities | 9609 | implemented (legacy ISIC group id) |

## Genuinely unimplemented, no successor yet (130)

`:spec`, `:repo nil`, and no `:superseded-by`/`:superseded-code` -- real gaps, not stale duplicates.

| ISIC | Name |
|---|---|
| 0128 | Growing of spices, aromatic, drug and pharmaceutical crops |
| 0129 | Growing of other perennial crops |
| 0144 | Raising of sheep and goats |
| 017 | Hunting, trapping and related service activities |
| 0170 | Hunting, trapping and related service activities |
| 024 | Support services to forestry |
| 0240 | Support services to forestry |
| 0899 | Other mining and quarrying n.e.c. |
| 1313 | Finishing of textiles |
| 1392 | Manufacture of made-up textile articles, except apparel |
| 1393 | Manufacture of carpets and rugs |
| 1399 | Manufacture of other textiles n.e.c. |
| 142 | Manufacture of articles of fur |
| 1420 | Manufacture of articles of fur |
| 143 | Manufacture of knitted and crocheted apparel |
| 1430 | Manufacture of knitted and crocheted apparel |
| 1512 | Manufacture of luggage, handbags and the like, saddlery and... |
| 2029 | Manufacture of other chemical products n.e.c. |
| 2391 | Manufacture of refractory products |
| 2393 | Manufacture of other porcelain and ceramic products |
| 2396 | Cutting, shaping and finishing of stone |
| 2399 | Manufacture of other non-metallic mineral products n.e.c. |
| 2513 | Manufacture of steam generators, except central heating hot... |
| 252 | Manufacture of weapons and ammunition |
| 2520 | Manufacture of weapons and ammunition |
| 2815 | Manufacture of ovens, furnaces and furnace burners |
| 2823 | Manufacture of machinery for metallurgy |
| 2829 | Manufacture of other special-purpose machinery |
| 304 | Manufacture of military fighting vehicles |
| 3040 | Manufacture of military fighting vehicles |
| 329 | Other manufacturing n.e.c. |
| 3290 | Other manufacturing n.e.c. |
| 3315 | Repair of transport equipment, except motor vehicles |
| 429 | Construction of other civil engineering projects |
| 4290 | Construction of other civil engineering projects |
| 452 | Maintenance and repair of motor vehicles |
| 4520 | Maintenance and repair of motor vehicles |
| 453 | Sale of motor vehicle parts and accessories |
| 4530 | Sale of motor vehicle parts and accessories |
| 454 | Sale, maintenance and repair of motorcycles and related p... |
| 4540 | Sale, maintenance and repair of motorcycles and related par... |
| 4661 | Wholesale of solid, liquid and gaseous fuels and related pr... |
| 4719 | Other retail sale in non-specialized stores |
| 472 | Retail sale of food, beverages and tobacco in specialized... |
| 4721 | Retail sale of food in specialized stores |
| 4722 | Retail sale of beverages in specialized stores |
| 4723 | Retail sale of tobacco products in specialized stores |
| 4742 | Retail sale of audio and video equipment in specialized stores |
| 475 | Retail sale of other household equipment in specialized s... |
| 4751 | Retail sale of textiles in specialized stores |
| 4752 | Retail sale of hardware, paints and glass in specialized st... |
| 4753 | Retail sale of carpets, rugs, wall and floor coverings in s... |
| 4759 | Retail sale of electrical household appliances, furniture, ... |
| 476 | Retail sale of cultural and recreation goods in specializ... |
| 4761 | Retail sale of books, newspapers and stationary in speciali... |
| 4762 | Retail sale of music and video recordings in specialized st... |
| 4763 | Retail sale of sporting equipment in specialized stores |
| 4764 | Retail sale of games and toys in specialized stores |
| 4771 | Retail sale of clothing, footwear and leather articles in s... |
| 4773 | Other retail sale of new goods in specialized stores |
| 478 | Retail sale via stalls and markets |
| 4781 | Retail sale via stalls and markets of food, beverages and t... |
| 4782 | Retail sale via stalls and markets of textiles, clothing an... |
| 4789 | Retail sale via stalls and markets of other goods |
| 479 | Retail trade not in stores, stalls or markets |
| 4791 | Retail sale via mail order houses or via Internet |
| 4799 | Other retail sale not in stores, stalls or markets |
| 491 | Transport via railways |
| 4921 | Urban and suburban passenger land transport |
| 4922 | Other passenger land transport |
| 4923 | Freight transport by road |
| 493 | Transport via pipeline |
| 4930 | Transport via pipeline |
| 501 | Sea and coastal water transport |
| 5012 | Sea and coastal freight water transport |
| 5021 | Inland passenger water transport |
| 5022 | Inland freight water transport |
| 511 | Passenger air transport |
| 512 | Freight air transport |
| 5120 | Freight air transport |
| 522 | Support activities for transportation |
| 531 | Postal activities |
| 5310 | Postal activities |
| 552 | Camping grounds, recreational vehicle parks and trailer p... |
| 5520 | Camping grounds, recreational vehicle parks and trailer parks |
| 5621 | Event catering |
| 5629 | Other food service activities |
| 5630 | Beverage serving activities |
| 581 | Publishing of books, periodicals and other publishing act... |
| 5811 | Book publishing |
| 5812 | Publishing of directories and mailing lists |
| 5813 | Publishing of newspapers, journals and periodicals |
| 5819 | Other publishing activities |
| 591 | Motion picture, video and television programme activities |
| 5911 | Motion picture, video and television programme production a... |
| 5912 | Motion picture, video and television programme post-product... |
| 5913 | Motion picture, video and television programme distribution... |
| 5914 | Motion picture projection activities |
| 592 | Sound recording and music publishing activities |
| 5920 | Sound recording and music publishing activities |
| 601 | Radio broadcasting |
| 602 | Television programming and broadcasting activities |
| 771 | Renting and leasing of motor vehicles |
| 772 | Renting and leasing of personal and household goods |
| 7722 | Renting of video tapes and disks |
| 773 | Renting and leasing of other machinery, equipment and tan... |
| 7730 | Renting and leasing of other machinery, equipment and tangi... |
| 774 | Leasing of intellectual property and similar products, ex... |
| 7740 | Leasing of intellectual property and similar products, exce... |
| 791 | Travel agency and tour operator activities |
| 799 | Other reservation service and related activities |
| 7990 | Other reservation service and related activities |
| 801 | Private security activities |
| 802 | Security systems service activities |
| 803 | Investigation activities |
| 811 | Combined facilities support activities |
| 8110 | Combined facilities support activities |
| 812 | Cleaning activities |
| 8129 | Other building and industrial cleaning activities |
| 813 | Landscape care and maintenance service activities |
| 821 | Office administrative and support activities |
| 8211 | Combined office administrative service activities |
| 822 | Activities of call centres |
| 823 | Organization of conventions and trade shows |
| 8230 | Organization of conventions and trade shows |
| 8292 | Packaging activities |
| 981 | Undifferentiated goods-producing activities of private ho... |
| 9810 | Undifferentiated goods-producing activities of private hous... |
| 982 | Undifferentiated service-producing activities of private ... |
| 9820 | Undifferentiated service-producing activities of private ho... |
