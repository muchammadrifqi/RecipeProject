import requests
from django.shortcuts import render
from django.conf import settings
from django.http import Http404

def index(request):
    return render(request, 'search.html')

def results(request):
    keyword = request.GET.get('keyword', '').strip()
    diet = request.GET.get('diet', '').strip()
    sort_by = request.GET.get('sort', '').strip()  # Ambil parameter sorting

    if not keyword:
        return render(request, 'results.html', {'recipes': []})

    # API credentials (pastikan di settings.py sudah benar)
    CONSUMER_KEY = getattr(settings, 'FATSECRET_CONSUMER_KEY', '')
    CONSUMER_SECRET = getattr(settings, 'FATSECRET_CONSUMER_SECRET', '')

    # FatSecret API endpoint
    base_url = "https://platform.fatsecret.com/rest/server.api"

    # OAuth2 token
    try:
        token_response = requests.post(
            "https://oauth.fatsecret.com/connect/token",
            data={"grant_type": "client_credentials", "scope": "basic"},
            auth=(CONSUMER_KEY, CONSUMER_SECRET),
        )
        access_token = token_response.json().get("access_token")
    except Exception:
        access_token = None

    recipes = []
    if access_token:
        # Tambahkan diet ke search query jika ada
        search_query = f"{keyword} {diet}" if diet else keyword
        
        params = {
            "method": "recipes.search",
            "format": "json",
            "search_expression": search_query,
            "max_results": 20  # Ambil lebih banyak untuk sorting
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = requests.get(base_url, params=params, headers=headers)
            data = response.json()
            results = data.get("recipes", {}).get("recipe", [])

            # Normalize hasil agar selalu list
            if isinstance(results, dict):
                results = [results]

            # Fetch nutrition data untuk setiap recipe (jika sorting diaktifkan)
            for r in results:
                recipe_data = {
                    "recipe_id": r.get("recipe_id"),
                    "recipe_name": r.get("recipe_name"),
                    "recipe_description": r.get("recipe_description", "No description."),
                    "recipe_image": r.get("recipe_image", None),
                    "calories": None,  # Default None
                }
                
                # Jika user memilih sorting, fetch nutrition data
                if sort_by in ['calories_asc', 'calories_desc']:
                    try:
                        nutrition_params = {
                            "method": "recipe.get",
                            "format": "json",
                            "recipe_id": r.get("recipe_id"),
                        }
                        nutrition_response = requests.get(base_url, params=nutrition_params, headers=headers)
                        nutrition_data = nutrition_response.json()
                        
                        # Ambil data serving
                        serving_data = nutrition_data.get("recipe", {}).get("serving_sizes", {}).get("serving", {})
                        if isinstance(serving_data, list) and len(serving_data) > 0:
                            serving_data = serving_data[0]
                        
                        if isinstance(serving_data, dict):
                            calories = serving_data.get("calories")
                            recipe_data["calories"] = float(calories) if calories else 0
                    except Exception as e:
                        print(f"Error fetching nutrition for recipe {r.get('recipe_id')}: {e}")
                        recipe_data["calories"] = 0
                
                recipes.append(recipe_data)
                
            # Sorting berdasarkan kalori
            if sort_by == 'calories_asc':
                recipes = sorted(recipes, key=lambda x: x['calories'] if x['calories'] is not None else float('inf'))
            elif sort_by == 'calories_desc':
                recipes = sorted(recipes, key=lambda x: x['calories'] if x['calories'] is not None else 0, reverse=True)
                
        except Exception as e:
            print("FatSecret Error:", e)

    context = {
        "recipes": recipes,
        "selected_sort": sort_by,
        "selected_diet": diet,
        "keyword": keyword
    }
    return render(request, 'results.html', context)



def detail(request, recipe_id):
    CONSUMER_KEY = getattr(settings, 'FATSECRET_CONSUMER_KEY', '')
    CONSUMER_SECRET = getattr(settings, 'FATSECRET_CONSUMER_SECRET', '')

    # Dapatkan token lagi (aman kalau expired)
    try:
        token_response = requests.post(
            "https://oauth.fatsecret.com/connect/token",
            data={"grant_type": "client_credentials", "scope": "basic"},
            auth=(CONSUMER_KEY, CONSUMER_SECRET),
        )
        access_token = token_response.json().get("access_token")
    except Exception:
        access_token = None
    
    recipe_data = {}
    if access_token:
        params = {
            "method": "recipe.get",
            "format": "json",
            "recipe_id": recipe_id,
        }
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = requests.get("https://platform.fatsecret.com/rest/server.api", params=params, headers=headers)
            data = response.json()
            recipe = data.get("recipe", {})
            img_from_results = request.GET.get('img')

            recipe_data = {
                "recipe_id": recipe.get("recipe_id"),
                "recipe_name": recipe.get("recipe_name", "Unknown Recipe"),
                "recipe_description": recipe.get("recipe_description", "No description."),
                "recipe_image": recipe.get("recipe_image", img_from_results),
                "ingredients": [],
                "instructions": [],
                "nutrition": {},
                "serving_size": "",
                "all_nutrition": {}  # Untuk semua data nutrisi
            }

            # Ingredients
            ingredients_data = recipe.get("ingredients", {}).get("ingredient", [])
            if isinstance(ingredients_data, dict):
                ingredients_data = [ingredients_data]
            recipe_data["ingredients"] = [i.get("ingredient_description") for i in ingredients_data]

            # Directions
            directions_data = recipe.get("directions", {}).get("direction", [])
            if isinstance(directions_data, dict):
                directions_data = [directions_data]
            recipe_data["instructions"] = [d.get("direction_description") for d in directions_data]

            # Nutrition - Process all nutrition data
            serving_data = recipe.get("serving_sizes", {}).get("serving", {})
            
            # Jika serving adalah list, ambil yang pertama
            if isinstance(serving_data, list) and len(serving_data) > 0:
                serving_data = serving_data[0]
            
            # Simpan semua data nutrisi
            if isinstance(serving_data, dict):
                recipe_data["serving_size"] = serving_data.get("serving_size", "")
                recipe_data["all_nutrition"] = serving_data
                
                # Untuk FDA panel, simpan nutrisi utama dengan format yang tepat
                recipe_data["nutrition"] = {
                    "Calories": serving_data.get("calories"),
                    "Fat": serving_data.get("fat"),
                    "Protein": serving_data.get("protein"),
                    "Carbohydrate": serving_data.get("carbohydrate"),
                    "Fiber": serving_data.get("fiber"),
                    "Sugar": serving_data.get("sugar"),
                    "Sodium": serving_data.get("sodium"),
                    "Cholesterol": serving_data.get("cholesterol"),
                    "Saturated_Fat": serving_data.get("saturated_fat"),
                    "Trans_Fat": serving_data.get("trans_fat"),
                }

        except Exception as e:
            print("Error fetching recipe details:", e)
            raise Http404("Recipe not found.")

    if not recipe_data:
        raise Http404("Recipe not found or unavailable.")

    return render(request, 'details.html', {'recipe': recipe_data})