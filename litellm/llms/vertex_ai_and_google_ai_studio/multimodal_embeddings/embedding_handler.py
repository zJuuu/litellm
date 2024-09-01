import json
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

import httpx

import litellm
from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler, HTTPHandler
from litellm.llms.vertex_ai_and_google_ai_studio.gemini.vertex_and_google_ai_studio_gemini import (
    VertexAIError,
    VertexLLM,
)
from litellm.types.llms.vertex_ai import (
    Instance,
    InstanceVideo,
    VertexMultimodalEmbeddingRequest,
)


class VertexMultimodalEmbedding(VertexLLM):
    def __init__(self) -> None:
        super().__init__()
        self.SUPPORTED_MULTIMODAL_EMBEDDING_MODELS = [
            "multimodalembedding",
            "multimodalembedding@001",
        ]

    def multimodal_embedding(
        self,
        model: str,
        input: Union[list, str],
        print_verbose,
        model_response: litellm.EmbeddingResponse,
        custom_llm_provider: Literal["gemini", "vertex_ai"],
        optional_params: dict,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        logging_obj=None,
        encoding=None,
        vertex_project=None,
        vertex_location=None,
        vertex_credentials=None,
        aembedding=False,
        timeout=300,
        client=None,
    ):
        auth_header, url = self._get_token_and_url(
            model=model,
            gemini_api_key=api_key,
            vertex_project=vertex_project,
            vertex_location=vertex_location,
            vertex_credentials=vertex_credentials,
            stream=None,
            custom_llm_provider=custom_llm_provider,
            api_base=api_base,
            should_use_v1beta1_features=False,
            mode="embedding",
        )

        if client is None:
            _params = {}
            if timeout is not None:
                if isinstance(timeout, float) or isinstance(timeout, int):
                    _httpx_timeout = httpx.Timeout(timeout)
                    _params["timeout"] = _httpx_timeout
            else:
                _params["timeout"] = httpx.Timeout(timeout=600.0, connect=5.0)

            sync_handler: HTTPHandler = HTTPHandler(**_params)  # type: ignore
        else:
            sync_handler = client  # type: ignore

        optional_params = optional_params or {}

        request_data = VertexMultimodalEmbeddingRequest()

        if "instances" in optional_params:
            request_data["instances"] = optional_params["instances"]
        elif isinstance(input, list):
            vertex_instances: List[Instance] = self.process_openai_embedding_input(
                _input=input
            )
            request_data["instances"] = vertex_instances

        else:
            # construct instances
            vertex_request_instance = Instance(**optional_params)

            if isinstance(input, str):
                vertex_request_instance["text"] = input

            request_data["instances"] = [vertex_request_instance]

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {auth_header}",
        }

        ## LOGGING
        logging_obj.pre_call(
            input=input,
            api_key="",
            additional_args={
                "complete_input_dict": request_data,
                "api_base": url,
                "headers": headers,
            },
        )

        if aembedding is True:
            return self.async_multimodal_embedding(
                model=model,
                api_base=url,
                data=request_data,
                timeout=timeout,
                headers=headers,
                client=client,
                model_response=model_response,
            )

        response = sync_handler.post(
            url=url,
            headers=headers,
            data=json.dumps(request_data),
        )

        if response.status_code != 200:
            raise Exception(f"Error: {response.status_code} {response.text}")

        _json_response = response.json()
        if "predictions" not in _json_response:
            raise litellm.InternalServerError(
                message=f"embedding response does not contain 'predictions', got {_json_response}",
                llm_provider="vertex_ai",
                model=model,
            )
        _predictions = _json_response["predictions"]

        model_response.data = _predictions
        model_response.model = model

        return model_response

    async def async_multimodal_embedding(
        self,
        model: str,
        api_base: str,
        data: VertexMultimodalEmbeddingRequest,
        model_response: litellm.EmbeddingResponse,
        timeout: Optional[Union[float, httpx.Timeout]],
        headers={},
        client: Optional[AsyncHTTPHandler] = None,
    ) -> litellm.EmbeddingResponse:
        if client is None:
            _params = {}
            if timeout is not None:
                if isinstance(timeout, float) or isinstance(timeout, int):
                    timeout = httpx.Timeout(timeout)
                _params["timeout"] = timeout
            client = AsyncHTTPHandler(**_params)  # type: ignore
        else:
            client = client  # type: ignore

        try:
            response = await client.post(api_base, headers=headers, json=data)  # type: ignore
            response.raise_for_status()
        except httpx.HTTPStatusError as err:
            error_code = err.response.status_code
            raise VertexAIError(status_code=error_code, message=err.response.text)
        except httpx.TimeoutException:
            raise VertexAIError(status_code=408, message="Timeout error occurred.")

        _json_response = response.json()
        if "predictions" not in _json_response:
            raise litellm.InternalServerError(
                message=f"embedding response does not contain 'predictions', got {_json_response}",
                llm_provider="vertex_ai",
                model=model,
            )
        _predictions = _json_response["predictions"]

        model_response.data = _predictions
        model_response.model = model

        return model_response

    def process_openai_embedding_input(
        self, _input: Union[list, str]
    ) -> List[Instance]:
        """
        Process the input for multimodal embedding requests.

        Args:
            _input (Union[list, str]): The input data to process.

        Returns:
            List[Instance]: A list of processed VertexAI Instance objects.
        """

        _input_list = None
        if not isinstance(_input, list):
            _input_list = [_input]
        else:
            _input_list = _input

        processed_instances = []
        for element in _input:
            if not isinstance(element, dict):
                # assuming that input is a list of strings
                # example: input = ["hello from litellm"]
                instance = Instance(text=element)
            else:
                # assume this is a
                instance = Instance(**element)
            processed_instances.append(instance)

        return processed_instances