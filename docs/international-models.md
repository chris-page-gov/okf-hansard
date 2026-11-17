# Parliamentary records and controlled vocabularies

Researched on 17 November 2026 for the Westminster pilot.

| Model | Relevant practice | Pilot decision |
| --- | --- | --- |
| UK Parliament subject indexing | The Indexing and Data Management Section maintains Parliament’s SKOS controlled vocabulary. The Parliamentary Digital Service describes a business graph for parliamentary objects and a topic graph for subject indexing. | Keep people, offices, Bills and proceedings distinct from subject concepts. Use UK Parliament identifiers where verified and maintain a local term scheme for pilot alias rules. |
| European Parliament open data and EPVOC | The API distinguishes plenary meetings, individual speech and speech-related activities, documents, procedures and adopted texts. EPVOC supplies parliamentary properties, including a speech identifier. ELI-EP and ORG-EP model legislation, processes and organisations. | Keep the sitting, agenda section, contribution and legislative procedure independently addressable. Preserve identifiers across stages and link the Bill to its specific proceeding. |
| European Parliament debate indexing and EuroVoc | The Parliament’s methodological tables use EuroVoc descriptors to index debates and adopted texts. EuroVoc is a multilingual SKOS thesaurus maintained by the EU Publications Office. | Treat policy subjects as governed concepts with preferred and alternate labels. Add EuroVoc mappings where individual scope notes and terms can be checked. |
| Ireland and Akoma Ntoso | The Oireachtas publishes debate and written question data as official Akoma Ntoso XML. The model distinguishes debate sections, speech, the speaker and the capacity in which they spoke. AKN distinguishes the work from its published expressions and formats. | Retain an item locator, a stable identity and an observed version. Store the reported capacity separately from the person and effective appointment. |
| Parla-CLARIN and ParlaMint | The TEI-based encoding models structured proceedings, speaker references and annotated text spans across several parliaments. ParlaMint applies tighter corpus rules and publishes linguistic annotations. | Capture text offsets and the normalisation algorithm for each match. Treat entity annotations as an inspectable layer over Parliament’s source. |
| Canada’s LiPaD and the joint DiLiPaD programme | LiPaD linked digitised Canadian House of Commons speeches with parliamentarian and biographical data. DiLiPaD research covered Canada, the UK and the Netherlands. | Use dated membership and representation when relating a person to a seat or party. Retain coverage details for each source edition. |
| European Parliament proceedings as Linked Open Data | The research linked proceedings at speech level with members, country data and topics to support more specific searches. | Direct contribution-to-entity links are the reusable unit. Compute earlier shared mentions from an inverted index with the source evidence for every result. |

## Primary sources

- [UK Parliament controlled vocabulary](https://api.parliament.uk/vocabulary/browser) and [PDS modelling account](https://pds.blog.parliament.uk/2016/09/09/modelling-parliaments/)
- [European Parliament Open Data API](https://data.europarl.europa.eu/en/developer-corner/opendata-api), [EPVOC](https://europarl.github.io/epvoc/2.1.0/) and [European Parliament application profiles](https://data.europarl.europa.eu/en/developer-corner)
- [European Parliament debate indexing](https://www.europarl.europa.eu/cre/tables_info_en.htm), [EuroVoc dataset](https://data.europa.eu/data/datasets/eurovoc) and [W3C SKOS reference](https://www.w3.org/TR/skos-reference/)
- [Oireachtas official data API](https://api.oireachtas.ie/), [Oireachtas debate encoding](https://github.com/Oireachtas/ontology/wiki/Debates-body) and [OASIS Akoma Ntoso vocabulary](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0-part1-vocabulary.pdf)
- [Parla-CLARIN specification](https://clarin-eric.github.io/parla-clarin/) and [ParlaMint corpus encoding](https://clarin-eric.github.io/ParlaMint/)
- [University of Toronto LiPaD evidence](https://dhn.utoronto.ca/linked-parliamentary-data-project-lipad/) and [DiLiPaD project account](https://www.cs.utoronto.ca/~gh/research-pages/research-parliament.html)
- [Van Aggelen and colleagues on debates as Linked Open Data](https://ir.cwi.nl/pub/25250) and [W3C Web Annotation vocabulary](https://www.w3.org/TR/annotation-vocab/)

## What the pilot implements

The YAML-LD graph contains the provenance-bearing relationship assertions of the OKF Explorer Bundle Wiki profile. Text evidence records the source API response digest, field pointer and normalised text offsets. Calendar and structural coverage use Parliament’s APIs. The pilot lexicon combines official Members and Bills labels, published post titles and a curated list of entities and topics. The international mappings in this report are conceptual comparisons.

Each connection between a contribution and an entity is counted once for the history view. All matched offsets remain available behind that count. Editorial date bounds, licence and scope metadata accompany the view.

The Foundry warm-up and build prompts informed the domain profile, competency questions, source coverage, independent facets, evidence-bearing graph, consumer check and release receipts. This local derivative has its own profile and assurance record. See the [domain profile](../profile/domain.yaml) and [UI research](voice-and-visual-ui.md).
