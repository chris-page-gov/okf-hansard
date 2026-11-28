# Repeat the November retrieval experiment

## Check the published results

Read the [beginner report](report.md) or follow a [casebook question](casebook.md) to the original Hansard contributions. A clean checkout contains the frozen questions, the passages each search returned, the two models’ decisions and answers, and the scores for all 58 trials. To verify their checksums and reproduce the scores from those files, run the following command from the repository root with Python 3.12. This check runs offline, without the SSD or model weights.

```sh
python3 -B -m unittest discover -s tests -p test_november_retrieval.py -v
```

## Repeat the searches and model inference

The full experiment runs on Apple Silicon. Phase one reads published parliamentary material and provisions pinned public model weights. In phase two the macOS network sandbox encloses the search, decision and writing processes. No API key is needed. Model files and derived indexes belong on a drive with sufficient space.

1. Start with the Hansard repository and the verified publication receipt at commit `41a340e06ec02b7d5d4d5802e893534697328d32`. Use its matching local capture, release and site directories. The published site provides coverage and source links. Reconstructing this exact full-text experiment also requires the hash-verified capture used to build that release.
2. Extract `scripts` and `experiments/reference-consumer` from Hansard main commit `e374ed9f7702c81693851a273d4ce3aab9923099` to the `upstream` directory beside these scripts. This pins the capture reader, model profiles, status instructions, writer and sandbox supervisor. From the experiment directory in a clean checkout, run the following commands before importing the runners.

   ```sh
   mkdir upstream
   git -C ../.. archive e374ed9f7702c81693851a273d4ce3aab9923099 scripts experiments/reference-consumer | tar -xf - -C upstream
   ln -s ../upstream voice/upstream
   ```

3. Install the versions in [environment.txt](environment.txt) in a dedicated Python 3.12 environment. Create an empty `<store>/model` directory on the SSD. Use `python provision_e5.py <store>/model` to acquire and verify the inference weights and tokenizer from the public E5 revision. The script checks each file against the [public model-file checksums](e5-checksums.txt). The weights use SHA-256. The smaller files use Git blob object IDs. The original llama.cpp b11556 binaries and OpenJev and Bonsai weights are specified in the upstream profiles.
4. Use `prepare.py <publication.json> <store>` to create `corpus.jsonl`. It verifies the source files, full contribution count and per-House counts. Check the resulting digest against [the frozen protocol](protocol.json). Use the supplied `questions.json` and `queries.json` for an exact replay. Only `queries.json`, with no reference answers or source IDs, feeds search and answer generation.
5. Run `python retrieval.py --store <store> --output <store>/index-02` with the E5 environment. Store the E5 files in `<store>/model`. It builds both indexes, encodes all passages, checks the vector norms and similarity range, runs both searches and records the isolated worker probes.
6. Run `python answer.py --index <store>/index-02 --output <store>/answers-01 --binary <llama-server> --weights <OpenJev-GGUF> --writer-binary <llama-completion> --writer-weights <Bonsai-GGUF>`. The supervisor verifies the model and binary digests. It runs OpenJev, unloads it, then runs Bonsai. The underlying question, output fields, generation seed and rendering rules are shared across each pair. Unlike the earlier format test, each retrieval method can return different passages.
7. Run `score.py <index-directory> <answer-directory>` to compare the outputs with the sealed-off answer key. The scoring program checks the frozen question file hash and writes `scores.json`.

The supervised workers require a macOS session that permits Seatbelt and the supervisor's one authorised loopback request per run. The benchmark stops on failed isolation checks or budget overruns. Under the previous test's rules, a denial requires a handling-policy citation. This public corpus contains no private handling-policy record. A denial therefore withholds the writer output.

The query set is source-led. The author inspected a deterministic sample of anchored contributions and wrote new questions before looking at either method's rankings. The sample selected one record per available date and House from attributed contributions with 44–105 words, a number in the text and a multiword debate title. It excluded several topics from the earlier benchmark. The choice within each eligible group minimised SHA-256 of “retrieval-round1” plus the source route. The questions are new to this experiment. A comparison of training corpora was outside its scope.

[Question selection and reference answers](questions.json) · [Original search and scoring plan](protocol.json) · [Public E5 model](https://huggingface.co/intfloat/e5-small-v2/tree/ffb93f3bd4047442299a41ebb6fa998a38507c52) · [Hansard runner and model profiles](https://github.com/chris-page-gov/okf-hansard/tree/e374ed9f7702c81693851a273d4ce3aab9923099/experiments/reference-consumer)

## Additional conversational questions

The primary retrieval results showed a ceiling on questions containing explicit speaker or institution clues. Before any further look-ups, eight new questions and their reference answers were frozen in [voice/questions.json](voice/questions.json). These used all eligible source records for an independent sample: every other sitting date in the primary date list, alternating Commons and Lords. The selection excluded titles in the first source sample. It used the same attributed, contribution-anchored, numeric-text eligibility rules with a 42–105 word range and chose the smallest hash of “voice-holdout-1” plus the route. One date and House combination had no qualifying record. Questions omitted the speaker's name and used a conversational style. No phone recording or speech transcription formed part of this search experiment.

Run `followup_search.py --store <store> --output <store>/voice-index` using the second, numerically checked primary index at `<store>/index-02`. It opens the SQLite index read-only, memory-maps the saved E5 vectors, reproduces all 42 original top-three lists and then handles the new queries. Run `voice/answer.py` with the same model files and its own output directory, then `voice/score.py` with the new index and answers. The two answer runners and scoring programs are byte-identical. The score tables distinguish the two question sets.

The primary run's first vector multiplication emitted floating-point warnings on macOS. The second build explicitly summed each vector product and checked that all similarity values were finite and within the possible cosine range. It returned the same three passages in the same order for every original question and method. All reported answers use the checked build.
