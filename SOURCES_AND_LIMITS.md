# Tableau interfaces and product limits

Implementation decisions were checked against Tableau's official documentation on 2026-09-05.

- REST publishing: https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_ref_publishing.htm
- Publishing resources and packaged-workbook requirements:
  https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_concepts_publish.htm
- REST authentication and PAT guidance:
  https://help.tableau.com/current/api/rest_api/en-us/REST/rest_api_concepts_auth.htm
- Tableau Server Client for Python:
  https://tableau.github.io/server-client-python/docs/api-ref.html
- Tableau Hyper API: https://tableau.github.io/hyper-db/docs/
- Tableau Public publishing and public-data warning:
  https://help.tableau.com/current/pro/desktop/en-us/publish_workbooks_tableaupublic.htm

PromptBI does not generate Tableau workbook XML from scratch. Tableau's Document API describes
programmatic updates to existing workbook/data-source files and does not support creating files
from scratch. PromptBI instead creates supported Hyper extracts and publishes those as data
sources; users build or maintain workbook presentation in Tableau Desktop/Public Edition.

The app does not claim that correlations are causal or that baseline forecasts and rankings are
validated decisions. Prescriptive optimization requires explicit objective functions, constraints,
costs, uncertainty, and domain approval; those cannot be inferred safely from arbitrary uploads.

