import os
import base64
import requests
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
import openai
import logging
#from format_ouput import format_color_analysis

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

openai.api_key = os.getenv("OPENAI_API_KEY")
#CUSTOM_PROMPT = os.getenv("ANALYSIS_PROMPT")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

UPLOAD_FOLDER = 'tmp'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error encoding image: {str(e)}")
        raise

def analyze_image_colors(image_path):
    try:
        base64_image = encode_image(image_path)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai.api_key}"
        }

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text":"From this image, provide a detailed color analysis in the following format: Exact skin tone, Precise hair color description, Specific eye color, List exactly 5 hex color codes that would be most flattering based on these features, with: Hex code, Color name, Where to wear it (top, bottom, accessory). Keep responses concise and focused only on the person in this specific image. No general color theory or guidelines. please output the result by grouping the skintone, eyecolor, and hair color together each on a new line, and the colors and hex codes in the same way."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 300
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload
        )

        if not response.ok:
            logging.error(f"OpenAI API error: {response.text}")
            raise Exception(f"OpenAI API error: {response.status_code}")

        response_data = response.json()
        result = response_data['choices'][0]['message']['content']
        print(result)

        # parsed_result = {
        #     'skin_undertone': 'Warm undertone',  # Extract from response
        #     'hair_color': 'Deep black hair with a slight sheen',  # Extract from response
        #     'eye_color': 'Dark brown',  # Extract from response
        #     'colors': [
        #         # Extract from response
        #         {'name': 'Peach', 'hex': '#FFCC99', 'wear': 'Top'},
        #         {'name': 'Lavender Purple', 'hex': '#6F4A8E', 'wear': 'Bottom'},
        #         {'name': 'Light Olive Green', 'hex': '#B3D99C', 'wear': 'Accessory'},
        #         {'name': 'Coral', 'hex': '#FF6F61', 'wear': 'Top'},
        #         {'name': 'Sky Blue', 'hex': '#4B9CD3', 'wear': 'Bottom'}
        #     ]
        # }

        # # Format the result
        # formatted_result = format_color_analysis(parsed_result)
        # return formatted_result

        if 'choices' not in response_data or not response_data['choices']:
            raise Exception("Unexpected API response format")

        return response_data['choices'][0]['message']['content']

    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error analyzing image: {str(e)}")
        raise

def format_output(response_text):
    parsed_data_values = {
        'skin_undertone': ' ',
        'hair_color': ' ',
        'eye_color': ' ',
        'recommended_colors': []
    }

    lines = response_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

    line = line.lstrip('- ')
    line = line.replace('**', '')

    if 'Skin Undertone' in line:
        parsed_data_values['skin_undertone'] = line.split(':', 1)[1].strip
    elif 'Hair Color' in line:
        parsed_data_values['hair_color'] = line.split(':', 1)[1].strip
    elif 'Eye Color' in line:
        parsed_data_values['eye_color'] = line.split(':', 1)[1].strip

    elif '#' in line:
        parts = line.split(',')
        if len(parts) >= 3:
            hex = parts[0].strip()
            color_name = parts[1].strip()
            where_to_wear = parts[2].strip()

            parsed_data_values['recommended_colors'].append({
                'hex': hex,
                'name': color_name,
                'wear': where_to_wear
            })

            return parsed_data_values

@app.route('/')
def index():
    return send_file('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        try:
            file.save(filepath)
            initial_response = analyze_image_colors(filepath)
            parsed_data = format_output(initial_response)
            response_data = {
                'initial_analysis': initial_response,
                'parsed_data': {
                    'skin_undertone': parsed_data['skin_undertone'],
                    'hair_color': parsed_data['hair_color'],
                    'eye_color': parsed_data['eye_color'],
                    'recommended_colors': parsed_data['recommended_colors']
                },
                'success': True
            }

            return jsonify(response_data)

        finally:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError as e:
                    logging.error(f"Error removing temporary file: {str(e)}")

    except Exception as e:
        logging.error(f"Error in /analyze endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500




if __name__ == "__main__":
    app.run(debug=True)