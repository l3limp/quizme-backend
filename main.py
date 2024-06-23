import json
import base64

from crewai import Crew, Agent, Task, Process
import os
from pydantic import BaseModel

import logging
import pdfplumber

from flask import Flask, jsonify, request
from flask_restful import Api, Resource


app = Flask(__name__)
api = Api(app)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class FlashCard(BaseModel):
    question: str
    answer: str
    question_number: int

class QuestionsList(BaseModel):
    questions: list[FlashCard]
    
    
def generate_quiz(num_of_questions, path, text):
    
    quiz_question_generator = Agent(
        role='Quiz Question Generator',
        goal='Create quiz questions and short answers based on content provided.',
        backstory='You are adept at generating relevant questions and concise answers from given information. You make the quiz from the following text: {text}',
    )
    
    quiz_editor = Agent(
        role='Quiz Editor',
        goal='Edit the quiz questions and answers into a structured document.',
        backstory='You work on the questions and answers created by the Quiz Question Generator. You excel at organizing information into clear and structured formats.',
    )
    
    generate_questions_task = Task(
        description='Generate a list of {num_of_questions} quiz questions and short answers based on the provided text.',
        expected_output='A list of {num_of_questions} quiz questions and corresponding short answers.',
        agent=quiz_question_generator
    )
    
    format_quiz_task = Task(
        description='Format the generated quiz questions and answers into a readable quiz. Only provide {num_of_questions} questions and corresponding answers',
        expected_output='A well-formatted quiz with {num_of_questions} questions.',
        output_json=QuestionsList,
        agent=quiz_editor
    )
    
    crew = Crew(
        agents=[quiz_question_generator, quiz_editor],
        tasks=[generate_questions_task, format_quiz_task],
        process=Process.sequential
    )
    
    result = crew.kickoff(inputs = {'num_of_questions': num_of_questions, 'text': text})
    return json.loads(result)
    
def save_to_txt(file_path, first_page, last_page):
    text = []
    
    if first_page < 1:
        first_page = 1
    with pdfplumber.open(file_path) as pdf:
        pages = pdf.pages
        
        if first_page >= len(pages):
            first_page = len(pages)-1
        
        for i in range(first_page-1, last_page):
            if i >= len(pages):
                break
            
            lines = pages[i].extract_text_lines()
            for obj in lines:
                text.append(obj['text'])

    text = [txt for txt in text if (len(txt) > 16)]
    text = ' '.join(text)
    
    upload_dir = 'uploads/'
    txt_path = os.path.join(upload_dir, 'uploaded_file.txt')
    file = open(txt_path, 'w')
    file.write(text)
    return txt_path, text

    
class GetQuiz(Resource):

    def post(self):
        
        logger.info('Received event: %s', request)
        
        
        # body = event.get('body', {})
        # if event.get('isBase64Encoded', False):
        #     body = base64.b64decode(body)
            
        try:
            body = request.get_json()
            num_of_ques = body['num_of_ques']
            file_content = body['file']
            first_page = body['first_page']
            last_page = body['last_page']
            
            if not file_content:
                return jsonify({
                    'statusCode': 400,
                    'body': {'message': 'File not provided'}
                })

            file_data = base64.b64decode(file_content)

            upload_dir = 'uploads/'
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)

            file_path = os.path.join(upload_dir, 'uploaded_file.pdf')
            with open(file_path, 'wb') as file:
                file.write(file_data)
            txt_path = ''
            text = ''
            try: 
                txt_path, text = save_to_txt(file_path, first_page, last_page)
            except Exception as e:
                return jsonify({
                    'statusCode': 500,
                    'body': {'message': str(e), 'reason': 'Could not save as txt', 'path': file_path}
                })
            
            response = 'None'
            
            try: 
                if txt_path != '':
                    response = generate_quiz(num_of_ques, txt_path, text)
                else:
                    return jsonify({
                        'statusCode': 500,
                        'body': {'message': 'Could not get txt_path', 'reason': 'Failed at quiz gen'}
                    }  )
            except Exception as e:
                return jsonify({
                    'statusCode': 500,
                    'body': {'message': str(e), 'reason': 'Failed at quiz gen'}
                })   

            return {
                'statusCode': 200,
                'body': {
                        'output': response,
                        'first_page': first_page,
                        'last_page': last_page
                    },
            
            }

        except Exception as e:
            return jsonify({
                'statusCode': 500,
                'body': {'message': str(e), 'reason': 'I dont know'}
            })
            
api.add_resource(GetQuiz, '/getquiz')

if __name__ == "__main__":
    app.run(debug=True)
