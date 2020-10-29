import numpy as np
import os
import io

# import for server
from flask import Flask, render_template, request, Response, send_file, jsonify
from queue import Queue, Empty
import threading
import time

# import for model
from transformers import AutoTokenizer, AutoModelWithLMHead
import time

# flask server
app = Flask(__name__)

# limit input file size under 2MB

# model loading
tokenizer = AutoTokenizer.from_pretrained("gpt2-large")
model = AutoModelWithLMHead.from_pretrained("gpt2-large")

# request queue setting
requests_queue = Queue()
BATCH_SIZE = 1
CHECK_INTERVAL = 0.1

# static variable

# request handling
def handle_requests_by_batch():
    try:
        while True:
            requests_batch = []
            while not (len(requests_batch) >= BATCH_SIZE):
                try:
                    requests_batch.append(requests_queue.get(timeout=CHECK_INTERVAL))
                except Empty:
                    continue
                
            batch_outputs = []

            for request in requests_batch:
                batch_outputs.append(run(request["input"][0], request["input"][1], request["input"][2]))

            for request, output in zip(requests_batch, batch_outputs):
                request["output"] = output

    except Exception as e:
        while not requests_queue.empty():
            requests_queue.get()
        print(e)


# request processing
threading.Thread(target=handle_requests_by_batch).start()

# run model
def run(num, length, prompt):
    try:
        prompt = prompt.strip()
        input_ids = tokenizer.encode(prompt, return_tensors='pt')
        min_length = len(input_ids.tolist()[0])
        length += min_length

        sample_outputs = model.generate(input_ids, pad_token_id=50256, 
                                        do_sample=True, 
                                        max_length=length, 
                                        min_length=length,
                                        top_k=40,
                                        num_return_sequences=num)

        generated_texts = []
        for i, sample_output in enumerate(sample_outputs):
            output = tokenizer.decode(sample_output.tolist()[min_length:], skip_special_tokens=True)
            generated_texts.append(output)
        
        return generated_texts

    except Exception as e:
        print(e)
        return 500

# routing
@app.route("/generation", methods=['POST'])
def generation():
    try:
        # only get one request at a time
        if requests_queue.qsize() > BATCH_SIZE:
            return jsonify({'message' : 'TooManyReqeusts'}), 429
    
        # check image format
        try:
            num = str(request.form['num'])
            length = str(request.form['length'])
            prompt = str(request.form['prompt'])
            num = int(num)
            length = int(length)
            
        except Exception:
            return jsonify({'message' : 'Error! Can not read length from request'}), 500

        # put data to request_queue
        req = {'input' : [num, length, prompt]}
        requests_queue.put(req)
        
        # wait output
        while 'output' not in req:
            time.sleep(CHECK_INTERVAL)
       
        # send output
        generated_text = req['output']
        
        if generated_text == 500:
            return jsonify({'message': 'Error! An unknown error occurred on the server'}), 500
        
        result = {}
        for i, text in enumerate(generated_text):
            result[i] = text
        
        result = jsonify(result)
        
        return result, 200
    
    except Exception as e:
        print(e)
        return jsonify({'message': 'Error! Unable to process request'}), 400

@app.route('/healthz')
def health():
    return "ok", 200

@app.route('/')
def main():
    return "ok", 200

if __name__ == "__main__":
    from waitress import serve
    serve(app, host='0.0.0.0', port=80)