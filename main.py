from dotenv import load_dotenv
import os
from PIL import Image
import io
from instagrapi import Client
import time
import logging
import httpx
import io

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_credentials():
    """Load Hugging Face and Instagram credentials from .env file."""
    try:
        load_dotenv()
        hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
        print(hf_token)
        ig_username = os.getenv("INSTAGRAM_USERNAME")
        ig_password = os.getenv("INSTAGRAM_PASSWORD")
        if not all([hf_token, ig_username, ig_password]):
            raise ValueError("Missing credentials in .env file")
        logger.info("Credentials loaded successfully")
        return {"hf_token": hf_token, "ig_username": ig_username, "ig_password": ig_password}
    except Exception as e:
        logger.error(f"Error loading credentials: {e}")
        raise

def generate_image(prompt, hf_token):
    """Generate image from Hugging Face API using StabilityAI Stable Diffusion 3.5 Large or any other model."""
    try:
        headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json",
            "Accept": "image/png"
        }

        payload = {
            "inputs": prompt
        }

        url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-3.5-large"

        response = httpx.post(url, headers=headers, json=payload, timeout=60.0)

        if response.status_code != 200:
            logging.error(f"HF API Error {response.status_code}: {response.text}")
            raise Exception(f"Image generation failed: {response.status_code}")

        logging.info("Image generated successfully from HF API")
        return response.content  # PNG image in bytes

    except Exception as e:
        logging.error(f"Error generating image: {repr(e)}")
        logging.warning("Generating placeholder image instead")
        placeholder = Image.new("RGB", (512, 512), color="gray")
        buffer = io.BytesIO()
        placeholder.save(buffer, format="PNG")
        return buffer.getvalue()


def save_image(image_data, output_dir="images", filename_prefix="post"):
    """Save image as JPG with Instagram-compatible size."""
    try:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(output_dir, f"{filename_prefix}_{timestamp}.jpg")

        image = Image.open(io.BytesIO(image_data))
        image = image.resize((1080, 1080), Image.LANCZOS)
        image = image.convert("RGB")
        image.save(file_path, "JPEG", quality=95)
        logger.info(f"Image saved to {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"Error saving image: {e}")
        raise

def init_instagram_client(username, password, session_file="ig_session.json"):
  """Initialize and authenticate Instagram client with session persistence."""
  try:
      cl = Client()
      cl.delay_range = [1, 5]  # Random delays to avoid detection

      if os.path.exists(session_file):
          cl.load_settings(session_file)
          try:
              cl.get_timeline_feed()  # Try a harmless call to validate session
              logger.info("Loaded existing Instagram session.")
              return cl
          except Exception:
              logger.warning("Session expired or invalid. Logging in again.")

      # Fallback to fresh login
      cl.login(username, password)
      cl.dump_settings(session_file)
      logger.info("Logged in and saved new Instagram session.")
      return cl

  except Exception as e:
      logger.error(f"Error initializing Instagram client: {e}")
      raise

def post_to_instagram(cl, image_path, caption):
    """Post image to Instagram with caption."""
    try:
        time.sleep(30)  # Delay to avoid automation detection
        media = cl.photo_upload(
            path=image_path,
            caption=caption
        )
        logger.info(f"Posted to Instagram, Media ID: {media.pk}")
        return media.pk
    except Exception as e:
        logger.error(f"Error posting to Instagram: {e}")
        raise

def main():
    """Main function to generate and post promotional image."""
    try:
        # Define prompt and caption
        prompt = "A sleek, modern web development workspace with a laptop displaying a vibrant website, surrounded by clean code snippets, glowing UI elements, and a futuristic digital background, professional and tech-inspired, high detail, 512x512 resolution"
        caption = "🚀 Elevate your online presence with our expert web development services! From stunning websites to powerful e-commerce platforms, we build your digital dreams. Contact us today! 🌐 #WebDevelopment #WebDesign #TechSolutions"

        # Load credentials
        creds = load_credentials()
        hf_token = creds["hf_token"]

        # Generate and save image
        image_data = generate_image(prompt, hf_token)
        image_path = save_image(image_data)

        # Initialize Instagram client and post
        ig_client = init_instagram_client(creds["ig_username"], creds["ig_password"])
        media_id = post_to_instagram(ig_client, image_path, caption)

        logger.info(f"Success! Posted promotional image with Media ID: {media_id}")
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise

if __name__ == "__main__":
    main()