import os
import sys
import logging
from pathlib import Path
import base64
from io import BytesIO
import torch
from torchvision import transforms
from torchvision.models import resnet50
from PIL import Image
try:
    from mcp.server.fastmcp import FastMCP
except Exception:
    # fallback: fastmcp may be installed as a top-level package
    from fastmcp import FastMCP


# Configure logging to stderr to avoid stdout pollution
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)

mcp = FastMCP("Bird-Predictor")

# Configuration avec chemins ABSOLUS
SCRIPT_DIR = Path(__file__).parent.absolute()
MODEL_PATH = str(SCRIPT_DIR / "model" / "resnet50_cub.pth")
CLASSES_PATH = str(SCRIPT_DIR / "classes.txt")

# Variables globales
model = None
class_names = None
device = None

def initialize_model():
    """Initialise le modèle au démarrage du serveur"""
    global model, class_names, device
    
    try:
        logging.info("🔄 Initialisation du modèle ResNet-50...")
        logging.info(f"📂 Répertoire du script: {SCRIPT_DIR}")
        logging.info(f"📂 Chemin du modèle: {MODEL_PATH}")
        logging.info(f"📂 Chemin des classes: {CLASSES_PATH}")
        
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Vérifier que les fichiers existent
        if not os.path.exists(MODEL_PATH):
            logging.error(f"❌ Modèle introuvable : {MODEL_PATH}")
            return False
        
        if not os.path.exists(CLASSES_PATH):
            logging.error(f"❌ Fichier classes introuvable : {CLASSES_PATH}")
            return False
        
        # Charger le modèle
        logging.info("📦 Chargement des poids du modèle...")
        model = resnet50(weights=None)
        model.fc = torch.nn.Linear(model.fc.in_features, 200)
        model.load_state_dict(torch.load(MODEL_PATH, map_location=device, weights_only=True))
        model.eval()
        model.to(device)
        logging.info(f"✅ Modèle chargé sur {device}")
        
        # Charger les classes
        with open(CLASSES_PATH, "r", encoding="utf-8") as f:
            class_names = [line.strip() for line in f.readlines()]
        logging.info(f"✅ {len(class_names)} classes d'oiseaux chargées")
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Erreur lors de l'initialisation : {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def load_image_from_source(image_source: str) -> Image.Image:
    """
    Charge une image depuis différentes sources :
    - Chemin de fichier local
    - Base64 string
    - URL (optionnel)
    
    Args:
        image_source: Chemin de fichier, base64 string, ou URL
        
    Returns:
        PIL Image object
    """
    try:
        # 1. Vérifier si c'est un chemin de fichier
        if os.path.exists(image_source):
            logging.info(f"📂 Chargement depuis le chemin: {image_source}")
            return Image.open(image_source).convert("RGB")
        
        # 2. Vérifier si c'est du base64
        if image_source.startswith("data:image"):
            # Format: data:image/png;base64,iVBORw0KG...
            logging.info("🔢 Détection d'une image en base64 avec préfixe data:image")
            base64_data = image_source.split(",", 1)[1]
            image_data = base64.b64decode(base64_data)
            return Image.open(BytesIO(image_data)).convert("RGB")
        
        # 3. Essayer de décoder directement en base64
        try:
            logging.info("🔢 Tentative de décodage base64 direct")
            image_data = base64.b64decode(image_source)
            return Image.open(BytesIO(image_data)).convert("RGB")
        except:
            pass
        
        # 4. Si rien ne fonctionne
        raise ValueError(f"Format d'image non supporté. Fournissez un chemin de fichier ou une image en base64.")
        
    except Exception as e:
        logging.error(f"❌ Erreur lors du chargement de l'image : {str(e)}")
        raise

@mcp.tool()
def predict_bird_species(image_source: str, top_k: int = 5) -> dict:
    """
    Prédit l'espèce d'oiseau à partir d'une image.
    
    Args:
        image_source (str): Chemin vers l'image OU image encodée en base64
        top_k (int): Nombre de prédictions à retourner (défaut: 5, max: 10).
    
    Returns:
        dict: Contient le statut, les prédictions avec espèces et niveaux de confiance.
    
    Exemples:
        - Avec chemin: predict_bird_species("/path/to/bird.jpg")
        - Avec base64: predict_bird_species("data:image/jpeg;base64,/9j/4AAQ...")
    """
    try:
        logging.info(f"📥 Requête de prédiction reçue")
        
        # Vérifier que le modèle est chargé
        if model is None or class_names is None:
            error_msg = "Le modèle n'est pas initialisé. Vérifiez les logs du serveur."
            logging.error(f"❌ {error_msg}")
            return {
                "status": "error",
                "message": error_msg,
                "model_path": MODEL_PATH,
                "classes_path": CLASSES_PATH
            }
        
        # Charger l'image depuis n'importe quelle source
        logging.info(f"📸 Chargement de l'image...")
        image = load_image_from_source(image_source)
        logging.info(f"📐 Taille de l'image: {image.size}")
        
        # Transform
        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])
        
        tensor = transform(image).unsqueeze(0).to(device)
        logging.info(f"📊 Tensor shape: {tensor.shape}")
        
        # Prédiction
        with torch.no_grad():
            outputs = model(tensor)
            probs = torch.nn.functional.softmax(outputs, dim=1)
            top_probs, top_indices = torch.topk(probs, k=min(top_k, 10))
        
        # Formatter les résultats
        predictions = []
        for prob, idx in zip(top_probs[0].cpu().numpy(), top_indices[0].cpu().numpy()):
            predictions.append({
                "species": class_names[int(idx)],
                "confidence": float(prob),
                "confidence_percent": f"{float(prob) * 100:.2f}%"
            })
        
        logging.info(f"✅ Prédiction réussie : {predictions[0]['species']} ({predictions[0]['confidence_percent']})")
        
        # Déterminer le type de source pour le message de retour
        source_type = "file_path" if os.path.exists(image_source) else "base64"
        
        return {
            "status": "success",
            "source_type": source_type,
            "image_size": f"{image.size[0]}x{image.size[1]}",
            "predictions": predictions,
            "top_prediction": predictions[0]["species"],
            "top_confidence": predictions[0]["confidence_percent"]
        }
        
    except Exception as e:
        error_msg = f"Erreur lors de la prédiction : {str(e)}"
        logging.error(f"❌ {error_msg}")
        import traceback
        logging.error(traceback.format_exc())
        return {
            "status": "error",
            "message": error_msg
        }

@mcp.tool()
def predict_bird_from_path(image_path: str, top_k: int = 5) -> dict:
    """
    Prédit l'espèce d'oiseau à partir d'un chemin de fichier.
    (Alias pour predict_bird_species avec validation stricte du chemin)
    
    Args:
        image_path (str): Chemin vers l'image de l'oiseau
        top_k (int): Nombre de prédictions à retourner (défaut: 5, max: 10).
    
    Returns:
        dict: Contient le statut, les prédictions avec espèces et niveaux de confiance.
    """
    if not os.path.exists(image_path):
        return {
            "status": "error",
            "message": f"Fichier introuvable : {image_path}"
        }
    
    return predict_bird_species(image_path, top_k)

@mcp.tool()
def predict_bird_from_base64(base64_image: str, top_k: int = 5) -> dict:
    """
    Prédit l'espèce d'oiseau à partir d'une image encodée en base64.
    (Alias pour predict_bird_species avec validation base64)
    
    Args:
        base64_image (str): Image encodée en base64 (avec ou sans préfixe data:image)
        top_k (int): Nombre de prédictions à retourner (défaut: 5, max: 10).
    
    Returns:
        dict: Contient le statut, les prédictions avec espèces et niveaux de confiance.
    """
    return predict_bird_species(base64_image, top_k)

@mcp.tool()
def check_model_status() -> dict:
    """
    Vérifie si le modèle est chargé et prêt.
    
    Returns:
        dict: Statut du modèle
    """
    logging.info("🔍 Vérification du statut du modèle...")
    
    if model is None or class_names is None:
        return {
            "status": "not_loaded",
            "message": "Modèle non initialisé. Vérifiez les chemins MODEL_PATH et CLASSES_PATH.",
            "script_directory": str(SCRIPT_DIR),
            "model_path": MODEL_PATH,
            "classes_path": CLASSES_PATH,
            "model_exists": os.path.exists(MODEL_PATH),
            "classes_exists": os.path.exists(CLASSES_PATH)
        }
    
    return {
        "status": "ready",
        "message": "Modèle chargé et prêt à l'utilisation",
        "script_directory": str(SCRIPT_DIR),
        "device": str(device),
        "num_classes": len(class_names),
        "cuda_available": torch.cuda.is_available(),
        "model_path": MODEL_PATH,
        "classes_path": CLASSES_PATH,
        "supported_inputs": ["file_path", "base64_string", "data_url"]
    }

@mcp.tool()
def list_bird_classes(limit: int = 20) -> dict:
    """
    Liste les classes d'oiseaux disponibles.
    
    Args:
        limit (int): Nombre maximum de classes à retourner (défaut: 20)
    
    Returns:
        dict: Liste des classes d'oiseaux
    """
    if class_names is None:
        return {
            "status": "error",
            "message": "Les classes ne sont pas chargées"
        }
    
    return {
        "status": "success",
        "total_classes": len(class_names),
        "sample_classes": class_names[:limit],
        "message": f"Affichage de {min(limit, len(class_names))} classes sur {len(class_names)}"
    }

if __name__ == "__main__":
    logging.info("🚀 Démarrage du serveur MCP Bird-Predictor...")
    logging.info(f"📂 Répertoire courant: {os.getcwd()}")
    logging.info(f"📂 Répertoire du script: {SCRIPT_DIR}")
    logging.info(f"📂 Model path: {MODEL_PATH}")
    logging.info(f"📂 Classes path: {CLASSES_PATH}")
    
    # Initialiser le modèle au démarrage
    success = initialize_model()
    
    if success:
        logging.info("✅ Serveur prêt à recevoir des requêtes")
        logging.info("✅ Formats supportés: chemin de fichier, base64, data URL")
    else:
        logging.warning("⚠️ Serveur démarré mais le modèle n'a pas pu être chargé")
        logging.warning("⚠️ Vérifiez que les fichiers model/resnet50_cub.pth et classes.txt existent")
    
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        logging.error(f"❌ Erreur du serveur : {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)