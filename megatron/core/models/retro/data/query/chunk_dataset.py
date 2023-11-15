# Copyright (c) 2023, NVIDIA CORPORATION.  All rights reserved.

import torch

# >>>
# from megatron import get_retro_args, print_rank_0
from megatron.core.datasets.blended_megatron_dataset_builder import BlendedMegatronDatasetBuilder
from megatron.core.datasets.blended_megatron_dataset_config import GPTDatasetConfig
from megatron.core.datasets.gpt_dataset import GPTDataset
# from megatron.core.models.retro.data.db.utils import get_indexed_dataset_infos
from megatron.core.models.retro.data.utils import (
    get_num_chunks_per_sample,
    print_rank_0,
)
# from megatron.training import (
#     build_train_valid_test_datasets as build_pretraining_train_valid_test_datasets,
#     update_train_iters,
# )

# from .utils import get_neighbor_dirname, get_query_dir

# from pretrain_gpt import is_dataset_built_on_rank
# <<<


class ChunkDataset(torch.utils.data.Dataset):
    '''Pretraining chunk dataset wraps a standard GPT dataset.

    This dataset conceptually divides each sample (e.g., length 2048)
    into chunks (e.g., length 64) and restructures them into a list of
    chunks (e.g., length num_samples * num_chunks_per_sample).
    '''

    def __init__(self, sample_dataset, chunk_length):

        super().__init__()

        self.sample_dataset = sample_dataset

        self.chunk_length = chunk_length
        self.n_chunks_per_sample = get_num_chunks_per_sample()
        self.n_samples = len(sample_dataset)
        self.n_chunks = self.n_samples * self.n_chunks_per_sample

    def __len__(self):
        return self.n_chunks

    def __getitem__(self, idx):

        # Convert global chunk index to global sample index & local chunk index.
        sample_idx = idx // self.n_chunks_per_sample
        chunk_idx = idx % self.n_chunks_per_sample

        # Extract sample data.
        sample = self.sample_dataset[sample_idx]
        sample_token_ids = sample["text"]
        sample_doc_ids = sample["document_ids"]

        # Chunk start/end token idxs.
        token_start_idx = chunk_idx * self.chunk_length
        token_end_idx = token_start_idx + self.chunk_length
        chunk_token_ids = sample_token_ids[token_start_idx:token_end_idx]

        # Sample.
        return {
            "doc_ids" : sample_doc_ids,
            "text" : chunk_token_ids,
        }


def verify_indexed_dataset_order():
    '''Verify pretraining order same as DB order.'''

    # >>>
    # args = get_retro_args()
    # <<<

    # DB dataset prefixes.
    db_indexed_dataset_infos = get_indexed_dataset_infos()
    db_prefixes = [ info["prefix"] for info in db_indexed_dataset_infos ]

    # Verify order & prefixes.
    assert len(env.config.data_path) >= 2, "blended dataset supported only."
    pretraining_prefixes = env.config.data_path[1:None:2]

    if len(db_prefixes) != len(pretraining_prefixes):
        raise Exception("inconsistent dataset count between db & pretraining.")
    if db_prefixes != pretraining_prefixes:
        raise Exception("inconsistent dataset order between db & pretraining.")


# >>>
# def core_gpt_dataset_config_from_retro_args(args):
#     return GPTDatasetConfig(
#         is_built_on_rank=is_dataset_built_on_rank,
#         random_seed=env.config.retro_gpt_seed,
#         sequence_length=env.config.retro_gpt_seq_length,
#         blend=env.config.retro_gpt_data_path,
#         split=env.config.retro_gpt_split,
#         path_to_cache=env.config.data_cache_path,
#         return_document_ids=env.config.retro_return_doc_ids
#     )
def core_gpt_dataset_config_from_retro_preprocessing_config(
    config,
    is_dataset_built_on_rank,
    return_document_ids,
):
    return GPTDatasetConfig(
        is_built_on_rank=is_dataset_built_on_rank,
        random_seed=config.retro_gpt_seed,
        sequence_length=config.retro_gpt_seq_length,
        blend=config.retro_gpt_data_path,
        split=config.retro_gpt_split,
        path_to_cache=config.retro_gpt_data_cache_path,
        return_document_ids=return_document_ids,
    )
# <<<


def train_valid_test_datasets_provider(data_config, train_val_test_num_samples):
    """Build train, valid, and test datasets."""

    print_rank_0('> building train, validation, and test datasets '
                 'for GPT ...')
    
    train_ds, valid_ds, test_ds = BlendedMegatronDatasetBuilder(
        GPTDataset,
        train_val_test_num_samples,
        data_config,
    ).build()
    print_rank_0("> finished creating pretrained GPT datasets ...")

    return train_ds, valid_ds, test_ds


# def get_chunk_dataset_map(env):
#     '''Get train, valid, test chunk datasets.'''

#     # Update train iters.
#     update_train_iters(args)

#     env.config.iteration = 0
#     env.config.consumed_train_samples = 0

#     # Verify indexed dataset order.
#     verify_indexed_dataset_order()

#     # Datasets.
#     print_rank_0(" > datasets.")
#     train_ds, valid_ds, test_ds = build_pretraining_train_valid_test_datasets(
#         train_valid_test_datasets_provider)

#     sample_dataset_map = {
#         "train" : train_ds,
#         "valid" : valid_ds,
#         "test" : test_ds,
#     }

#     # Info dict.
#     chunk_dataset_map = {
#         key : {
#             "neighbor_dir" : get_neighbor_dirname(key, sample_ds),
#             "data" : ChunkDataset(sample_ds, env.config.retro_gpt_chunk_length),
#         }
#         for key, sample_ds in sample_dataset_map.items() if sample_ds
#     }

#     return chunk_dataset_map
def get_chunk_dataset_map(env):
    '''Get train, valid, test chunk datasets.'''

    # Reset iteration.
    env.config.iteration = 0
    env.config.consumed_train_samples = 0

    # Verify indexed dataset order.
    verify_indexed_dataset_order()

    # Info dict.
    chunk_dataset_map = {
        key : {
            "neighbor_dir" : get_neighbor_dirname(key, sample_ds),
            "data" : ChunkDataset(sample_ds, env.config.retro_gpt_chunk_length),
        }
        for key, sample_ds in sample_dataset_map.items() if sample_ds
    }

    return chunk_dataset_map
