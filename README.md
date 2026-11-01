# Bachelors Thesis

Title: Analysis of the Prevalence and Vulnerability of Qt Deserialization in Open-Source Projects

Submission date: 18.08.2026

Publication date: 01.11.2026

## Note on this version
This is the published version of the thesis. Certain parts of the original submission, namely the
acknowledgments and the formal university documentation, have been redacted. In addition,
the links to the thesis repository have been updated to point to its current location. In
agreement with the affected projects (Krita, Tiled, and Qt), the 90-day disclosure period
described in the thesis was shortened, so this version is published earlier than originally
planned. The scientific content is otherwise unchanged from the submitted version.

## Setup

**Requirements:**
- Python3.14

**Commands:**
```
# Create Python virtual environment
python3 -m venv .venv

# Activate Python virtual environment (depends on OS)
source .venv/bin/activate       # macOS / Linux
.\.venv\Scripts\Activate.ps1    # Windows PowerShell
.venv\Scripts\activate.bat      # Windows cmd.exe

# Install dependencies
python3 -m pip install -r requirements.txt
```


## Prevalence Analysis

**Content:**
```
.
├── .env        <- CREATE THIS
├── 1_query.py
├── 2_scan.py
├── 3_rank.py
├── 4_evaluate.py
├── analysis
│   ├── potential_qt_projects.jsonl
│   ├── qdatastream_projects.jsonl
│   ├── ranked_qdatastream_projects.jsonl
│   ├── state.json
│   └── verified_qt_projects.jsonl
├── plots
│   ├── age_distribution_comparison.png
│   ├── age_vs_score_relationship.png
│   ├── project_counts.png
│   ├── qdatastream_usage_rate_per_year.png
│   └── score_distribution.png
└── requirements.txt
```

**Prerequisite:**
In order to use the GitHub API, you need an access token ([How to get one](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql#authenticating-with-a-personal-access-token)).


**Setup:**
```
cd prevalence_analysis

# Create a file called `.env` and add your GitHub token like this: GITHUB_TOKEN=XXX
touch .env

# Run pipeline
python3 1_query.py
python3 2_scan.py
python3 3_rank.py
python3 4_evaluate.py
```



## Vulnerability Analysis


**Content:**
```
.
├── case_study
│   ├── qtlocalpeer_exploit_1.py    <- KRITA/TILED EXPLOIT
│   └── qtlocalpeer_exploit_2.py    <- TILED EXPLOIT
├── checks
│   ├── W1_log.jsonl    <- WX_log.jsonl ARE LLM LOGS
│   ├── W1_time.txt
│   ├── W2_log.jsonl
│   ├── W2_time.txt
│   ├── W3_log.jsonl
│   ├── W3_time.txt
│   ├── generate_W1.sh
│   ├── generate_W2.sh
│   ├── generate_W3.sh
│   ├── generate_tests.sh
│   ├── joern               <- CONTAINS THE JOERN CHECKS 
│   ├── prompt_W1.md
│   ├── prompt_W2.md
│   ├── prompt_W3.md
│   ├── prompt_tests.md
│   ├── report.md
│   ├── test_log.jsonl
│   ├── test_time.txt
│   └── tests               <- CONTAINS THE TEST CASES
├── run_verification_tests.sh
├── static_analysis
│   ├── bitcoin_repo_data.json
│   ├── ranked_qdatastream_projects_incl_bitcoin.jsonl
│   ├── report.txt
│   ├── report_NPE.txt  <- OLD REPORT WITH W3 THAT PRODUCED A NULLPOINTER EXCEPTION
│   ├── results.jsonl
│   └── results_NPE.jsonl
├── static_analysis.py
├── verification_tests_2026-07-30.txt
└── vulnerability_examples                          <- EXAMPLES FOR THE VULNERABILITIES
    ├── example_read_raw_data                       <- W1+W2
    └── example_uncontrolled_resource_consumption   <- W1+W3
```


**Setup:**
```
cd vulnerability_analysis

# Run Joern checks against vulnerability examples
./run_verification_tests.sh


# Run the static analysis
python3 static_analysis.py

```
