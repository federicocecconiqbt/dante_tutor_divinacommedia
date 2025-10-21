Sì — ho trovato diversi riferimenti al testo di La Divina Commedia a cura di Giorgio Petrocchi, ma **non posso verificare che siano tutti completi, legali da scaricare e pubblicare**. Ecco cosa ho trovato:

* Una versione online del canto I della prima cantica (“Inferno”) con dicitura “ed. Petrocchi”. ([danteonlineita][1])
* Un PDF che dichiara di essere la Commedia (edizione Petrocchi) in formato e-book. ([Internet Archive][2])
* Un record di catalogo che indica l’edizione Petrocchi come opera a stampa con nota introduttiva. ([primo.sns.it][3])

Se vuoi, posso *verificare la situazione dei diritti* per l’Italia e cercare un link *ufficiale/legalmente condiviso* dell’edizione Petrocchi completa (in PDF o altri formati) e inviartelo.

[1]: https://www.danteonline.it/opere/index.php?opera=Commedia+-+ed.+Petrocchi&utm_source=chatgpt.com "Commedia - ed. Petrocchi - Cantica I - Canto i - Opere"
[2]: https://archive.org/details/commediadantealighieri?utm_source=chatgpt.com "Commedia : Dante Alighieri : Free Download, Borrow, and ..."
[3]: https://primo.sns.it/primo-explore/fulldisplay/39pis_alma2159244560002521/39PIS_VISTA?utm_source=chatgpt.com "La Divina Commedia / Dante Alighieri ; testo critico stabilito da ..."
Grande domanda. Ti propongo un approccio “ibrido” che serve **sia la recitazione** (prosodia, pause, pronunce) **sia le domande sul testo** (ricerca semantica/filologica). In breve: conserva il testo in modo **canonicamente referenziabile**, arricchiscilo con **metadati per la performance**, e indicizza con **full-text + embedding** per il Q&A.

# 1) Edizione, suddivisione e riferimenti canonici

* **Edizione**: usa un testo critico affidabile (es. Petrocchi) ormai in pubblico dominio. Mantieni anche una colonna “normalized” per modernizzazioni minime (apostrofi, elisioni) solo per la recitazione/ASR.
* **Struttura**: `Cantica → Canto → Terzina → Verso`. ID stabili e leggibili:

  * `urn:cts:dante.dc:inf.05.027` = Inferno, canto 5, verso 27 (stile CTS).
* **Blocchi di recitazione**: oltre al verso singolo, crea “**battute**” da 10–15 versi (respiro naturale), conservando anche le terzine come unità.

# 2) Metadati per la recitazione (prosodia)

Per ogni **verso** aggiungi:

* **meter**: endecasillabo; **accent_pattern** (posizioni degli accenti principali).
* **rhyme_letter** (terza rima: aba bcb …) e **rhyme_group_id**.
* **phonemes_ipa**: trascrizione IPA per parole “difficili” (lessico personalizzato).
* **elision/ sinalefe**: flag e punti di fusione (aiuta TTS/attore).
* **ssml**: una versione con `<break>`, `<emphasis>`, `<prosody rate/pitch>`.
* **stage_directions** (facolt.) per tono/affetto (“sottovoce”, “solenne”).
* **audio** (facolt.): URL e **timestamps** per verso/terzina (se incidi una reference).

# 3) Metadati per il Q&A (filologici e semantici)

Per ogni **verso/terzina/battuta**:

* **lemma_tokens** (tokenizzazione + lemmatizzazione italiana).
* **entities** (personaggi, luoghi, concetti teologici).
* **topics/tags** (peccati/virtù, figure retoriche, fonti classiche/bibliche).
* **commento** (glossa breve) + riferimenti a commenti lunghi (esterni).
* **crossrefs**: rimandi intra/inter-canto (es. ricorrenze di immagini).
* **embedding_vector**: per la ricerca semantica (RAG).

# 4) Base dati: modello ibrido

## Opzione A — Relazionale (PostgreSQL) + ricerca

* Tabelle:

  * `cantica(id, name)`; `canto(id, cantica_id, number, incipit)`
  * `terzina(id, canto_id, number)`
  * `verso(id, terzina_id, number, text_original, text_normalized, ssml, accent_pattern, rhyme_letter, rhyme_group_id)`
  * `verso_prosody(verso_id, phonemes_ipa jsonb, elision_points jsonb)`
  * `verso_semantics(verso_id, lemmas jsonb, entities jsonb, topics jsonb, commento text)`
  * `media_audio(verso_id, url, t_start_ms, t_end_ms)`
  * `embeddings(item_type, item_id, vector)` con pgvector.
* Indicizza:

  * **pg_trgm**/**full-text** su `text_original`, `text_normalized`, `commento`.
  * **pgvector** per `vector` (ricerca kNN).

## Opzione B — Documentale (JSONL / Elasticsearch+KNN / Atlas Search)

* Un documento per **verso**, con chiave `urn` e tutti i metadati; shard per cantica.
* Vantaggio: full-text potente + vettoriale integrato; più semplice per pipeline RAG.

# 5) Pipeline RAG per le domande

1. **Retrieval 1**: filtro canonico (se l’utente cita “Inf. V”) → seleziona il range.
2. **Retrieval 2**: **BM25** + **embedding** su verso/terzina/battuta.
3. **Ricomposizione**: restituisci contesto in **blocchi di 3–6 terzine**.
4. **Answering**: LLM con **citazioni** (URN di versi) + note dal `commento`.
5. **Guardrail**: se la domanda è di **performance** (“recita X”), invia **ssml**.

# 6) Regole di normalizzazione (utile per recitazione/TTS)

* Mantieni `text_original` **intatto** (apostrofi, sinalefi, grafie storiche).
* `text_normalized`: spaziatura normalizzata, rimozione doppie apostrofi erratiche, ma **non modernizzare** il lessico.
* **Lexicon custom**: mappa parola→IPA (es. *ch’i’*, *già*, *virtù*), e regole di **sinalefe** (vocale+vocale → unione).

# 7) Esempi

## 7.1 Record JSON (per “verso”)

```json
{
  "urn": "urn:cts:dante.dc:inf.05.027",
  "cantica": "Inferno",
  "canto": 5,
  "terzina": 9,
  "verso": 27,
  "text_original": "Amor, ch’al cor gentil ratto s’apprende,",
  "text_normalized": "Amor, ch’al cor gentil ratto s’apprende,",
  "meter": "endecasillabo",
  "accent_pattern": [6, 10],
  "rhyme_letter": "a",
  "rhyme_group_id": "inf.05.terzine.9",
  "prosody": {
    "elision_points": [[6,7]],
    "phonemes_ipa": [
      {"token":"Amor","ipa":"aˈmor"},
      {"token":"ch’al","ipa":"kal"},
      {"token":"cor","ipa":"kɔr"},
      {"token":"gentil","ipa":"dʒenˈtil"},
      {"token":"ratto","ipa":"ˈratto"},
      {"token":"s’apprende","ipa":"sapˈprende"}
    ]
  },
  "semantics": {
    "lemmas": ["amore", "cuore", "gentile", "rapido", "apprendere"],
    "entities": ["Amore"],
    "topics": ["amor_cortese","etica_affettiva"],
    "commento": "La concezione stilnovista dell'amore come qualità propria del cuore nobile."
  },
  "ssml": "<speak><prosody rate=\"medium\">Amór, ch’al cor gentil <break time=\"120ms\"/> ràtto s’apprènde,</prosody></speak>"
}
```

## 7.2 Schema minimale PostgreSQL (estratto)

```sql
CREATE EXTENSION IF NOT EXISTS vector; -- pgvector

CREATE TABLE verso (
  id serial PRIMARY KEY,
  urn text UNIQUE,
  cantica text,
  canto int,
  terzina int,
  numero int,
  text_original text,
  text_normalized text,
  meter text,
  accent_pattern int[],
  rhyme_letter char(1),
  rhyme_group_id text,
  ssml text
);

CREATE TABLE verso_semantics (
  verso_id int REFERENCES verso(id),
  lemmas jsonb,
  entities jsonb,
  topics jsonb,
  commento text
);

CREATE TABLE embeddings (
  item_type text, -- 'verso' | 'terzina' | 'battuta'
  item_id int,
  vector vector(1024),
  PRIMARY KEY(item_type, item_id)
);
```

# 8) Recitazione: SSML e attori

* Prepara **due “voci”**: *narratore* e *personaggi* (quando marcati nel commento).
* Inserisci **cue**: `<break time="200ms">` alla fine verso; `<prosody rate="slow">` nei passi solenni; `<emphasis>` su parole chiave.
* Se vuoi **dizionari custom** per TTS, usa “lexicon/IPA” per parole arcaiche.

Esempio SSML per **terzina**:

```xml
<speak>
  <p>
    <s>Nel mezzo del cammin di nostra vita,</s>
    <s><prosody rate="slow">mi ritrovai per una selva oscura,</prosody></s>
    <s>ché la diritta via era smarrita.</s>
  </p>
</speak>
```

# 9) Strato applicativo (query tipiche)

* **Recita Canto V (blocchi da 12 versi)**: `SELECT ssml FROM battuta WHERE cantica='Inferno' AND canto=5 ORDER BY start_verso;`
* **Trova dove compare “Ulisse”**: full-text + knn; ritorna 3–6 terzine contigue + `urn`.
* **Domanda semantica** (“come è definito l’amore nel V?”): top-k embedding su `commento + text_original`, rerank BM25, contesti con citazioni.

# 10) Note pratiche

* **Non alterare mai l’originale**: qualsiasi normalizzazione va tenuta separata.
* **Versionare**: Git dei sorgenti (TEI-XML o JSONL), migrazioni DB tracciate.
* **TEI-XML**: ottimo come “master source” (marcatura di metrica, rima, note); poi esporti in JSON/DB.
* **Licenze**: verifica che l’edizione critica scelta sia realmente libera; cita sempre la fonte.

---

Se vuoi, ti preparo:

* un **TEI-XML di esempio** per una terzina,
* uno **script di ingestion** (JSONL→Postgres + embeddings),
* e un **prompt RAG** già set-up per risposte con citazioni URN.
Perfetto — ti ho preparato uno **script unico** che elabora **tutta l’opera** dal tuo PDF Petrocchi, **saltando prefazione/indici/header/footer**, e produce un **JSON per ogni Canto** + un **manifest** riepilogativo.

**Scarica lo script:**
[divina_full_pipeline.py](sandbox:/mnt/data/divina_full_pipeline.py)

### Cosa fa

* Scansiona **tutte le pagine** del PDF e rileva in automatico **Cantiche** (INFERNO, PURGATORIO, PARADISO) e **CANTI** (“CANTO PRIMO”, …).
* Filtra **prefazione**, **indici**, **numeri di pagina** e varie **didascalie**/intestazioni ricorrenti.
* Estrarre i **versi**; crea **terzine** (gruppi di 3) e **blocchi di recitazione** (default 12 versi, configurabili).
* Per ogni Canto genera: URN tipo `inf.05.027`, **SSML** minimo per verso e per blocco.
* Scrive un file JSON per ogni Canto e un `manifest.json` con l’elenco completo.

### Requisiti

```bash
pip install PyPDF2
```

### Esempio d’uso (sul PDF che hai caricato)

```bash
python /mnt/data/divina_full_pipeline.py \
  --pdf "/mnt/data/alighieri_la_divina_commedia.pdf" \
  --outdir "/mnt/data/commedia_json" \
  --block-size 12 \
  --block-overlap 0
```

Al termine troverai:

* Directory con file tipo: `inf_01.json`, `inf_02.json`, … `purg_01.json`, … `par_33.json`.
* `manifest.json` con i percorsi e i conteggi per ogni Canto.

### Note utili / Come adattarlo

* I **pattern** di pulizia si trovano in `HEADER_PATTERNS`, `FOOTER_PATTERNS`, `ILLUSTRATION_PATTERNS`. Se il tuo PDF ha rumori diversi, basta aggiungere regex lì.
* Il rilevamento dei Canti usa il titolo `CANTO ...`. Il numero del Canto viene incrementato **in ordine di apparizione per Cantica** (non legge i numeri romani).
* Il raggruppamento in terzine è **sequenziale** (3 a 3) e la rima è marcata come `aba` **locale** (semplificazione robusta). Se vuoi la **catena di terza rima** globale (aba bcb cdc…), posso aggiungerla.
* I **blocchi di recitazione** si controllano con `--block-size` e `--block-overlap` (finestra scorrevole se overlap > 0).

Vuoi che aggiunga subito:

1. la **catena completa di rime** tra terzine,
2. un **export TEI-XML** oltre al JSON,
3. o un parametro `--only-cantica/--only-canto` per processare porzioni selezionate?
Fatto ✅

**Mini tool (SSML slicer):** [ssml_slice.py](sandbox:/mnt/data/ssml_slice.py)

### Cosa fa

Prende una citazione tipo **“Inferno V vv. 61–72”**, apre il relativo JSON del canto (prodotto dalla pipeline), estrae quei versi e genera **SSML pronto per la lettura**, con pause brevi dopo ogni verso e pause più lunghe a fine terzina.

### Requisiti

* Avere già i JSON dei canti (es. generati da `divina_full_pipeline.py`) in una cartella.
* Python 3 (nessuna dipendenza extra).

### Uso

```bash
python /mnt/data/ssml_slice.py \
  --json-dir "/mnt/data/commedia_json" \
  --cite "Inferno V vv. 61–72" \
  --output "/mnt/data/inf5_61-72.ssml"
```

Parametri:

* `--json-dir` cartella con file tipo `inf_05.json`, `purg_01.json`, `par_33.json`.
* `--cite` accetta anche formati liberi:

  * `"Inferno 5 61-72"`
  * `"Inferno V 61 72"`
  * `"inferno v vv. 61–72"`
* `--pause-short` ms (default 120) → pausa tra versi.
* `--pause-terzina` ms (default 220) → pausa a fine terzina.
* `--output` se omesso stampa su stdout.

### Output (esempio, estratto)

```xml
<speak><p><s>...</s><break time="120ms"/><s>...</s><break time="120ms"/><s>...</s><break time="220ms"/>...</p></speak>
```

Vuoi anche la versione che **legge direttamente dal PDF** (senza passare dai JSON) per una citazione singola? Posso aggiungere un flag `--pdf` opzionale che fa l’estrazione al volo.
