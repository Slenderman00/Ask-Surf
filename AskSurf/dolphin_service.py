from llama_cpp import Llama  # noqa: F401
import os
import time
from settings import load_settings
from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel
import asyncio
import torch
from diffusers import StableDiffusionPipeline
import random
import gc


class QuestionRequest(BaseModel):
    question: str
    cwd: str


class DolphinService:
    def __init__(self):
        self.llm = None
        self.image_model = None
        self.cwd = ""
        self.messages = [
            {
                "role": "system",
                "content": (
                    "You are a trained dolphin assistant named Surf. You can use the following tags: [R], [Y], [O], [G], [P], [B], [N]. Where [N] is normal. Users interact with you by running the 'surf' CLI command. Users can also pipe data to you using the format: echo 'Hello' | surf 'Do something with this'"
                ),
            },
            {
                "role": "system",
                "content": (
                    "The image tag format is: [I]description 1, description 2, description 3[/I]. This creates an image based on the descriptions and appends it to the text. Ensure you do not forget the closing tag."
                ),
            },
            {
                "role": "system",
                "content": (
                    "Image tags can be inserted into text like this: 'this is text [I]blue eyes, green hair, tall, blue sky[/I] this is more text [I]Large tree, dark, scary[/I]'. Note that text can contain multiple image tags."
                ),
            },
            {
                "role": "system",
                "content": (
                    "Use image tags when the user requests a drawing, picture, or image, try and use color tags without being prompted."
                ),
            },
        ]
        self.api_server = FastAPI()

        self.last_activity = time.time()

        self.last_response = None
        self.current_task = None

    async def check_inactivity(self):
        """Check if service has been inactive for 10 minutes"""
        while True:
            await asyncio.sleep(60)  # Check every minute
            if time.time() - self.last_activity > 600:  # 600 seconds = 10 minutes
                print("Inactive for 10 minutes, shutting down...")
                await self.kill()

    async def root(self):
        return {"message": "Dolphin Service API"}

    async def kill(self):
        os.kill(os.getpid(), 9)

    async def ask_question(self, request: QuestionRequest):
        self.last_activity = time.time()
        self.messages.append({
            "role": "user",
            "content": request.question
        })
        self.cwd = request.cwd

        print(f"Question received: {request.question}")

        # run ask_model in the background
        self.current_task = asyncio.create_task(self.ask_model())

        return {"message": "Question received"}

    async def get_status(self):
        """Non-blocking status check"""
        if self.current_task is None:
            return "processing"
        if not self.current_task.done():
            return "processing"
        # Ensure we have a response
        if self.last_response is None:
            return "processing"
        return self.last_response

    async def await_get_response(self):
        """Blocking wait for response"""
        if self.current_task is None:
            return "No question has been asked"
        return await self.current_task

    async def ask_model(self):
        resp = self.get_response()
        self.last_response = self.check_for_images(resp)
        return self.last_response

    def check_model(self):
        # unload the image model
        self.image_model = None
        torch.cuda.empty_cache()
        gc.collect()
        if self.llm is None:
            settings = load_settings()

            self.llm = Llama(
                model_path=settings["general"]["model_path"],
                verbose=settings["general"]["verbose"],
                n_ctx=settings["general"]["n_ctx"],
                n_gpu_layers=settings["general"]["n_gpu_layers"],
                use_nmap=settings["general"]["use_nmap"],
                use_mlock=settings["general"]["use_mlock"],
            )

    def get_response(self):
        self.check_model()

        output = ""
        for message in self.messages:
            output += f"<|im_start|>{message['role']}\n {message['content']}<|im_end|>\n"

        output += "<|im_start|>assistant\n"

        settings = load_settings()
        self.last_response = self.llm(output, max_tokens=settings["general"]["max_tokens"])['choices'][0]['text']
        print(self.last_response)
        return self.last_response

    def check_image_model(self):
        self.llm = None
        torch.cuda.empty_cache()
        gc.collect()
        if self.image_model is None:
            settings = load_settings()

            # get the float type
            torch_dtype = torch.float32
            if settings["image"]["torch_dtype"] == "torch.float32":
                torch_dtype = torch.float32
            elif settings["image"]["torch_dtype"] == "torch.float16":
                torch_dtype = torch.float16
            elif settings["image"]["torch_dtype"] == "torch.bfloat16":
                torch_dtype = torch.bfloat16

            pipe = StableDiffusionPipeline.from_pretrained(settings["image"]["model"], device=settings["image"]["device"], torch_dtype=torch_dtype, safety_checker=None)
            pipe = pipe.to(settings["image"]["device"])

            self.image_model = pipe

    def check_for_images(self, response):
        if "[IMAGE]" in response:
            image_tags = response.split("[IMAGE]")
            for i in range(1, len(image_tags)):
                image_description = image_tags[i].split("[/IMAGE]")[0]
                image = self.generate_image(image_description)
                # generate a random image id
                image_id = random.randint(1000, 9999)
                image.save(f"{self.cwd}/image_{image_id}.png")
                response = response.replace(f"[IMAGE]{image_description}[/IMAGE]", f"[IMAGE]{self.cwd}/image_{image_id}.png[/IMAGE]")
        return response

    def generate_image(self, image_description):
        # unload the current model
        self.llm = None
        self.check_image_model()

        # save the image to the self.cwd with a unique name
        settings = load_settings()
        #  num_inference_steps=settings["image"]["inference_steps"], guidance_scale=settings["image"]["guidance_scale"], height=512, width=512
        return self.image_model(image_description).images[0]

    def add_endpoint(self, endpoint, function, methods=None):
        """Add an endpoint to the API server
        Args:
            endpoint (str): URL path
            function (callable): Handler function
            methods (list, optional): HTTP methods. Defaults to None.
        """
        if methods is None:
            self.api_server.add_api_route(endpoint, function)
        else:
            self.api_server.add_api_route(endpoint, function, methods=methods)

    def add_endpoints(self):
        self.add_endpoint("/", self.root)
        self.add_endpoint("/status", self.get_status)
        self.add_endpoint("/response", self.await_get_response)
        self.add_endpoint("/ask", self.ask_question, methods=["POST"])
        self.add_endpoint("/kill", self.kill)

    async def start_server(self, socket_path="/tmp/dolphin.sock"):
        # Ensure old socket is removed
        if os.path.exists(socket_path):
            os.unlink(socket_path)

        asyncio.create_task(self.check_inactivity())

        config = uvicorn.Config(
            app=self.api_server,
            uds=socket_path,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


async def main():
    dolphin = DolphinService()
    dolphin.add_endpoints()
    await dolphin.start_server()

if __name__ == "__main__":
    asyncio.run(main())