import argparse
import json
from typing import Any

import tiktoken
from beartype import beartype

from open_flamingo import create_model_and_transforms
from huggingface_hub import hf_hub_download
import torch
from PIL import Image

from gradio_client import Client

from agent.prompts import *
from browser_env import Trajectory
from browser_env.actions import (
    Action,
    ActionParsingError,
    create_id_based_action,
    create_none_action,
    create_playwright_action,
)
from browser_env.utils import Observation, StateInfo
from llms import lm_config
from llms.providers.openai_utils import (
    generate_from_openai_chat_completion,
    generate_from_openai_completion,
)


class Agent:
    """Base class for the agent"""

    def __init__(self, *args: Any) -> None:
        pass

    def next_action(
        self, trajectory: Trajectory, intent: str, meta_data: Any
    ) -> Action:
        """Predict the next action given the observation"""
        raise NotImplementedError

    def reset(
        self,
        test_config_file: str,
    ) -> None:
        raise NotImplementedError


class TeacherForcingAgent(Agent):
    """Agent that follows a pre-defined action sequence"""

    def __init__(self) -> None:
        super().__init__()

    def set_action_set_tag(self, tag: str) -> None:
        self.action_set_tag = tag

    def set_actions(self, action_seq: str | list[str]) -> None:
        if isinstance(action_seq, str):
            action_strs = action_seq.strip().split("\n")
        else:
            action_strs = action_seq
        action_strs = [a.strip() for a in action_strs]

        actions = []
        for a_str in action_strs:
            try:
                if self.action_set_tag == "playwright":
                    cur_action = create_playwright_action(a_str)
                elif self.action_set_tag == "id_accessibility_tree":
                    cur_action = create_id_based_action(a_str)
                else:
                    raise ValueError(
                        f"Unknown action type {self.action_set_tag}"
                    )
            except ActionParsingError as e:
                cur_action = create_none_action()

            cur_action["raw_prediction"] = a_str
            actions.append(cur_action)

        self.actions: list[Action] = actions

    def next_action(
        self, trajectory: Trajectory, intent: str, meta_data: Any
    ) -> Action:
        """Predict the next action given the observation"""
        return self.actions.pop(0)

    def reset(
        self,
        test_config_file: str,
    ) -> None:
        with open(test_config_file) as f:
            ref_actions = json.load(f)["reference_action_sequence"]
            tag = ref_actions["action_set_tag"]
            action_seq = ref_actions["action_sequence"]
            self.set_action_set_tag(tag)
            self.set_actions(action_seq)


class PromptAgent(Agent):
    """prompt-based agent that emits action given the history"""

    @beartype
    def __init__(
        self,
        action_set_tag: str,
        lm_config: lm_config.LMConfig,
        prompt_constructor: PromptConstructor,
        model=None,
        image_processor=None,
        tokenizer=None,
    ) -> None:
        super().__init__()
        self.lm_config = lm_config
        self.prompt_constructor = prompt_constructor
        self.action_set_tag = action_set_tag
        self.model = model
        self.image_processor = image_processor
        self.tokenizer = tokenizer

    def set_action_set_tag(self, tag: str) -> None:
        self.action_set_tag = tag

    @beartype
    def next_action(
        self, trajectory: Trajectory, intent: str, meta_data: dict[str, Any]
    ) -> Action:
        prompt = self.prompt_constructor.construct(
            trajectory, intent, meta_data
        )
        lm_config = self.lm_config
        if lm_config.provider == "gradio":
            last_obs = trajectory[-1]["observation"] # get last state info dict from trajectory
            obs_image = Image.fromarray(last_obs["image"])
            img_filename = "example_imgs\\temp.png"
            obs_image.save(img_filename)
            print("prompt", prompt)
            response = self.model.predict(
				"example_imgs\\temp.png",	# str representing input in 'Input' Image component
				prompt,	# str representing input in 'Prompt' Textbox component
				lm_config.gen_config["max_tokens"],	# int | float representing input in 'Max length' Slider component
				lm_config.gen_config["temperature"],	# int | float representing input in 'Temperature' Slider component
				lm_config.gen_config["top_p"],	# int | float representing input in 'Top p' Slider component
				fn_index=1
            )         
            print("response", response)
        elif lm_config.provider == "huggingface":
            last_obs = trajectory[-1]["observation"] # get last state info dict from trajectory
            obs_image = Image.fromarray(last_obs["image"])
            example_image = Image.open("example_imgs\\hp_fax.PNG")
            vision_x = [self.image_processor(example_image).unsqueeze(0), self.image_processor(obs_image).unsqueeze(0)]
            vision_x = torch.cat(vision_x, dim=0)
            vision_x = vision_x.unsqueeze(1).unsqueeze(0)
            print("generating response")
            generated_text = self.model.generate(
                vision_x=vision_x,
                lang_x=prompt["input_ids"],
                attention_mask=prompt["attention_mask"],
                max_new_tokens=lm_config.gen_config["max_tokens"],
                num_beams=3,
            )
            response = self.tokenizer.decode(generated_text[0])
            print(response)

        elif lm_config.provider == "openai":
            if lm_config.mode == "chat":
                response = generate_from_openai_chat_completion(
                    messages=prompt,
                    model=lm_config.model,
                    temperature=lm_config.gen_config["temperature"],
                    top_p=lm_config.gen_config["top_p"],
                    context_length=lm_config.gen_config["context_length"],
                    max_tokens=lm_config.gen_config["max_tokens"],
                    stop_token=None,
                )
            elif lm_config.mode == "completion":
                response = generate_from_openai_completion(
                    prompt=prompt,
                    engine=lm_config.model,
                    temperature=lm_config.gen_config["temperature"],
                    max_tokens=lm_config.gen_config["max_tokens"],
                    top_p=lm_config.gen_config["top_p"],
                    stop_token=lm_config.gen_config["stop_token"],
                )
            else:
                raise ValueError(
                    f"OpenAI models do not support mode {lm_config.mode}"
                )
        else:
            raise NotImplementedError(
                f"Provider {lm_config.provider} not implemented"
            )

        try:
            parsed_response = self.prompt_constructor.extract_action(response)
            if self.action_set_tag == "id_accessibility_tree":
                action = create_id_based_action(parsed_response)
            elif self.action_set_tag == "playwright":
                action = create_playwright_action(parsed_response)
            else:
                raise ValueError(f"Unknown action type {self.action_set_tag}")

            action["raw_prediction"] = response

        except ActionParsingError as e:
            action = create_none_action()
            action["raw_prediction"] = response

        return action

    def reset(self, test_config_file: str) -> None:
        pass


def construct_llm_config(args: argparse.Namespace) -> lm_config.LMConfig:
    llm_config = lm_config.LMConfig(
        provider=args.provider, model=args.model, mode=args.mode
    )
    if args.provider == "openai":
        llm_config.gen_config["temperature"] = args.temperature
        llm_config.gen_config["top_p"] = args.top_p
        llm_config.gen_config["context_length"] = args.context_length
        llm_config.gen_config["max_tokens"] = args.max_tokens
        llm_config.gen_config["stop_token"] = args.stop_token
        llm_config.gen_config["max_obs_length"] = args.max_obs_length
    elif args.provider == "huggingface":
        llm_config.gen_config["temperature"] = args.temperature
        llm_config.gen_config["top_p"] = args.top_p
        llm_config.gen_config["context_length"] = args.context_length
        llm_config.gen_config["max_tokens"] = args.max_tokens
        llm_config.gen_config["stop_token"] = args.stop_token
        llm_config.gen_config["max_obs_length"] = args.max_obs_length
    elif args.provider == "gradio":
        llm_config.gen_config["temperature"] = args.temperature
        llm_config.gen_config["top_p"] = args.top_p
        llm_config.gen_config["context_length"] = args.context_length
        llm_config.gen_config["max_tokens"] = args.max_tokens
        llm_config.gen_config["stop_token"] = args.stop_token
        llm_config.gen_config["max_obs_length"] = args.max_obs_length
    else:
        raise NotImplementedError(f"provider {args.provider} not implemented")
    return llm_config


def construct_agent(args: argparse.Namespace) -> Agent:
    llm_config = construct_llm_config(args)

    agent: Agent
    if args.agent_type == "teacher_forcing":
        agent = TeacherForcingAgent()
    elif args.agent_type == "prompt":
        with open(args.instruction_path) as f:
            constructor_type = json.load(f)["meta_data"]["prompt_constructor"]
        # tokenizer = tiktoken.get_encoding(llm_config.model)
        # tokenizer = tiktoken.encoding_for_model(llm_config.model)
        prompt_constructor = eval(constructor_type)(
            args.instruction_path, lm_config=llm_config, tokenizer=None
        )
        llama_model = Client("http://llama-adapter.opengvlab.com/")
        agent = PromptAgent(
                action_set_tag=args.action_set_tag,
                lm_config=llm_config,
                prompt_constructor=prompt_constructor,
                model=llama_model,
                tokenizer=None,
            )
    elif args.agent_type == "generation":
        with open(args.instruction_path) as f:
            constructor_type = json.load(f)["meta_data"]["prompt_constructor"]

            flamingo_model, image_processor, flam_tokenizer = create_model_and_transforms(
                clip_vision_encoder_path="ViT-L-14",
                clip_vision_encoder_pretrained="openai",
                lang_encoder_path="anas-awadalla/mpt-7b",
                tokenizer_path="anas-awadalla/mpt-7b",
                cross_attn_every_n_layers=4
            )

            checkpoint_path = hf_hub_download("openflamingo/" + args.model, "checkpoint.pt")
            flamingo_model.load_state_dict(torch.load(checkpoint_path), strict=False)

            prompt_constructor = eval(constructor_type)(
                args.instruction_path, lm_config=llm_config, tokenizer=flam_tokenizer
            )
            agent = PromptAgent(
                action_set_tag=args.action_set_tag,
                lm_config=llm_config,
                prompt_constructor=prompt_constructor,
                model=flamingo_model,
                image_processor=image_processor,
                tokenizer=flam_tokenizer,
            )
    else:
        raise NotImplementedError(
            f"agent type {args.agent_type} not implemented"
        )
    return agent
