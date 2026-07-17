import azure.functions as func
import pandas as pd
import json
import logging
import os
import io
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()

_df_cache = None

def load_dataframe():
    global _df_cache
    if _df_cache is not None:
        return _df_cache
    conn_str = os.environ["STORAGE_CONNECTION_STRING"]
    blob_service = BlobServiceClient.from_connection_string(conn_str)
    blob_client = blob_service.get_blob_client(container="datasets", blob="All_Diets.csv")
    csv_bytes = blob_client.download_blob().readall()
    df = pd.read_csv(io.BytesIO(csv_bytes))
    numeric_cols = df.select_dtypes(include="number").columns
    df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].mean())
    _df_cache = df
    return df


@app.route(route="GetNutritionalInsights", auth_level=func.AuthLevel.ANONYMOUS)
def GetNutritionalInsights(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("GetNutritionalInsights triggered")
    try:
        df = load_dataframe()
        avg_macros = df.groupby("Diet_type")[["Protein(g)", "Carbs(g)", "Fat(g)"]].mean().round(1)
        correlation = df[["Protein(g)", "Carbs(g)", "Fat(g)"]].corr().round(2)
        result = {"average_macros_by_diet": avg_macros.to_dict(orient="index"), "correlation_matrix": correlation.to_dict()}
        return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200)
    except Exception as e:
        logging.error(f"Error in GetNutritionalInsights: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), mimetype="application/json", status_code=500)


@app.route(route="GetRecipes", auth_level=func.AuthLevel.ANONYMOUS)
def GetRecipes(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("GetRecipes triggered")
    try:
        df = load_dataframe()
        diet_filter = req.params.get("diet_type")
        filtered = df if not diet_filter else df[df["Diet_type"].str.lower() == diet_filter.lower()]
        distribution = df["Diet_type"].value_counts().to_dict()
        top_recipes = filtered.sort_values("Protein(g)", ascending=False).head(5)[["Recipe_name", "Diet_type", "Protein(g)", "Carbs(g)", "Fat(g)"]].to_dict(orient="records")
        result = {"recipe_distribution_by_diet": distribution, "top_protein_recipes": top_recipes}
        return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200)
    except Exception as e:
        logging.error(f"Error in GetRecipes: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), mimetype="application/json", status_code=500)


@app.route(route="GetClusters", auth_level=func.AuthLevel.ANONYMOUS)
def GetClusters(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("GetClusters triggered")
    try:
        df = load_dataframe()
        # NOTE: now includes Fat(g) alongside Protein(g)/Carbs(g) so the frontend
        # can compute a real, per-diet Protein/Carbs/Fat correlation (heatmap).
        sample = df.groupby("Diet_type").apply(
            lambda g: g.sample(min(10, len(g)))[["Protein(g)", "Carbs(g)", "Fat(g)"]].to_dict(orient="records")
        ).to_dict()
        return func.HttpResponse(json.dumps(sample), mimetype="application/json", status_code=200)
    except Exception as e:
        logging.error(f"Error in GetClusters: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), mimetype="application/json", status_code=500)
