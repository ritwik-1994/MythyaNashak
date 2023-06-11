import os
from googletrans import Translator
from langchain.agents import load_tools, initialize_agent, AgentType
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import requests
import easyocr
from transcription_service import transcribe_audio
from pydub import AudioSegment


app = Flask(__name__)

# Set API keys
os.environ["SERPER_API_KEY"] = "d605fe88ed5370764f64cb81e9eb49b21457a18e"
os.environ["OPENAI_API_KEY"] = "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"

# Initialize LLM
llm = OpenAI(temperature=0)

# Load tools
tools = load_tools(["google-serper", "llm-math"], llm=llm)

# Initialize agent
agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True)

# Define response schemas
response_schemas = [
    ResponseSchema(name="claim", description="original question posed for fact checking"),
    ResponseSchema(name="Fact Check", description="True or False. Based on the final conclusion of the validity of the information."),
    ResponseSchema(name="Explanation", description="Detailed reasoning as to why provided information is True or False. Provide relevant information for your response as well.")
]

# Initialize output parser
output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
format_instructions = output_parser.get_format_instructions()

def convert_ogg_to_wav(ogg_file: str, wav_file: str):
    audio = AudioSegment.from_ogg(ogg_file)
    audio.export(wav_file, format="wav")

def translate_to_english(text):
    translator = Translator()
    try:
        translated = translator.translate(text, dest='en')
        return translated.text, translated.src
    except Exception as e:
        print(f"Error: {e}")
        return None

def retranslate_text(text, target_language):
    translator = Translator()
    try:
        translated = translator.translate(text, dest=target_language)
        return translated.text
    except Exception as e:
        print(f"Error: {e}")
        return None

def fact_check(user_input):
    translated_text, original_language = translate_to_english(user_input)
    user_input = translated_text

    internet_result = agent.run(user_input)

    template = "You are MithyaNashak, a large language model trained by IndianAI to Fact Check information provided to you, and avoid misformation spreading to Indian users. Take the inputs and provide a detailed reasoning as to why provided information is True or False. Provide relevant information for each point present in the user input and justification for your response to each of those points. User provided inputs is {user_input} and internet provided inputs is {internet_result}. \n{format_instructions} "

    prompt = PromptTemplate(input_variables=['user_input', 'internet_result'], template=template, partial_variables={"format_instructions": format_instructions})

    llm_chain = LLMChain(llm=llm, prompt=prompt)

    response = llm_chain.run({'user_input': user_input, 'internet_result': internet_result})

    try:
        return output_parser.parse(response)
    except:
        return response

def extract_text(image_path):
    # Create an EasyOCR reader with the desired language (English in this case)
    supported_languages = ['en', 'hi']
    reader = easyocr.Reader(supported_languages)

    # Read the text from the image
    result = reader.readtext(image_path)

    # Extract the recognized text from the result
    extracted_text = ' '.join([item[1] for item in result])

    return extracted_text



@app.route('/sms', methods=['POST'])
def sms_reply():
    # Get the message sent to your Twilio number
    message_body = request.form['Body']
    print(request.form)
    num_media = int(request.form['NumMedia'])

    if num_media == 0:
        user_input = message_body
    elif num_media == 1 and str(request.form['MediaContentType0']) == 'image/jpeg':
        image_url = request.form['MediaUrl0']
        response = requests.get(image_url)
        # Save the image with a filename
        filename = "downloaded_image.jpg"
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        user_input = extract_text('downloaded_image.jpg')

    elif num_media == 1 and str(request.form['MediaContentType0']) == 'audio/ogg':
        audio_url = request.form['MediaUrl0']
        response = requests.get(audio_url)
        # Save the audio with a filename
        filename = "downloaded_audio.ogg"
        with open(filename, 'wb') as f:
            f.write(response.content)
        ogg_filename = "downloaded_audio.ogg"
        wav_filename = "downloaded_audio.wav"
        convert_ogg_to_wav(ogg_filename, wav_filename)
        user_input = transcribe_audio(wav_filename)

    user_input, ori_lang = translate_to_english(user_input)
    # Process the message (e.g., convert to uppercase)
    result = fact_check(user_input)
    try:

        claim = retranslate_text(result['claim'],ori_lang)
        check_result = retranslate_text(result['Fact Check'], ori_lang)
        explanation_result = retranslate_text(result['Explanation'], ori_lang)
        response = f"Claim: {claim} \n\n\n Fact Check: {check_result} \n\n\nExplanation: {explanation_result}"
        print(result['Fact Check'])
        if result['Fact Check'] == False:
            response = f"{response} + \n\n\n Alert: This information is incorrect. 🚩Kindly ask the sender to stop forwarding it and to fact-check messages before sharing. Misinformation can harm society. Verify info by sending it to WhatsApp at +14155238886." 

    except:
        response = retranslate_text(result, ori_lang)

    # Create a TwiML response
    account_sid = 'AC69172b0a26c3e357ee6090e073d23c4d'
    auth_token = 'dc4af8c2c1042bdc2c15439464755b6b'
    client = Client(account_sid, auth_token)

    message = client.messages.create(
        from_='whatsapp:+14155238886',
        body=response,
        to='whatsapp:+917728086673'
        )

    return True


if __name__ == "__main__":
    #user_input = """शरद पवार ने एनसीपी के स्थापना दिवस के मौके पर दो कार्यकारी अध्यक्ष बनाए जाने की घोषणा की है. इनमें सुप्रिया सुले और प्रफुल्ल पटेल को ये जिम्मेदारी सौं... https://www.aajtak.in/india/news/story/sharad-pawar-ncp-ajit-pawar-supriya-sule-prafull-patel-maharashtra-politics-ntc-1712752-2023-06-10"""
    #image_path = '/Users/ritwikchakradhar/Documents/MithyaNashak/What.jpeg'
    #user_input = extract_text(image_path)
    app.run(debug=True, port = 5002)
    #user_input = """Union Home Minister Amit Shah strongly criticized Congress leader Rahul Gandhi for his recent remarks made during his visit to the United States, accusing him of using the trip as a mere vacation to avoid the scorching summer temperatures and unjustly criticize the nation. Rahul baba, in an attempt to evade the summer heat, has chosen to embark on an overseas vacation. However, it is disheartening to witness his continuous disparagement of our beloved country on foreign soil. I humbly urge Rahul Gandhi to draw inspiration from his esteemed ancestors," stated Amit Shah passionately while addressing a rally in the city of Patan, Gujarat."""
    #result = fact_check(user_input)
    #print(result)