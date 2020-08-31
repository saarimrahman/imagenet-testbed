import os
from os.path import join, exists
import argparse
import pathlib

import click
import numpy as np
import pandas as pd

import download_data
import dataframe
import plotter
from model_types import NatModelTypes, nat_model_types_map


def get_model_type(df_row):
    return nat_model_types_map[df_row.name]


def show_in_plot(df_row, option):
    model_name, model_type = df_row.name.lower(), df_row.model_type
    if option == 'only-standard':
        return 'subsample' not in model_name and df_row['val-on-vid-robust-classes'] >= 92 and model_type == NatModelTypes.STANDARD
    if option == 'no-subsample':
        return 'subsample' not in model_name and df_row.val >= 55        
    return 'subsample' not in model_name and df_row['val-on-vid-robust-classes'] >= 92


def use_for_line_fit(df_row):
    model_name, model_type, in_plot = df_row.name.lower(), df_row.model_type, df_row.show_in_plot
    return 'aws' not in model_name and 'batch64' not in model_name and model_type is NatModelTypes.STANDARD and in_plot


@click.command()
@click.option('--x_axis', type=str, default='val-on-vid-robust-classes')
@click.option('--y_axis', type=str, default='imagenet-vid-robust_pm0')
@click.option('--transform', type=str, default='logit')
@click.option('--num_bootstrap_samples', type=int, default=1000) 
@click.option('--output_dir', type=str, default=str((pathlib.Path(__file__).parent / '../outputs').resolve()))
@click.option('--output_file_dir', type=str, default=str((pathlib.Path(__file__).parent / '../paper/figs').resolve()))
@click.option('--skip_download', is_flag=True, type=bool)
@click.option('--option', type=str, default='')
def generate_xy_plot(x_axis, y_axis, transform, num_bootstrap_samples, output_dir, output_file_dir, skip_download, option):

    if skip_download:
        filename = join(output_dir, 'grid_df.pkl')
        if not exists(filename):
            raise Exception(f'Downloaded data not found at {filename}. Please run python src/plotting/download_data.py first')
        df = pd.read_pickle(filename)
    else:
        df = download_data.download_plotting_data(output_dir, store_data=True, verbose=True)

    df, df_metadata = dataframe.extract_metadata(df)
    df, df_metadata = dataframe.replace_10percent_with_metadata(df, df_metadata)
    df, df_metadata = dataframe.aggregate_corruptions_with_metadata(df, df_metadata)


    if option == 'no-subsample':
        x_axis = 'val'
    df = prepare_df_for_plotting(df, df_metadata, [x_axis, y_axis], option)
    df = plotter.add_plotting_data(df, [x_axis, y_axis])

    # auto set xlim and ylim based on visible points
    df_visible = df[df.show_in_plot == True]
    if option == 'no-subsample':
        xlim = [df_visible[x_axis].min() - 1, df_visible[x_axis].max() + 1]
    else:
        xlim = [df_visible[x_axis].min() - 1, df_visible[x_axis].max() + 0.1]
    if option == 'show-yx':
        ylim = [df_visible[y_axis].min() - 2, df_visible[[x_axis, y_axis]].values.max() + 0.1]
    else:
        ylim = [df_visible[y_axis].min() - 2, df_visible[y_axis].values.max() + 2]

    x_label = 'ImageNet' if option=='no-subsample' else 'ImageNet (class-subsampled)'
    fig, _ = plotter.model_scatter_plot(df, x_axis, y_axis, xlim, ylim, NatModelTypes, 
                                         transform=transform, num_bootstrap_samples=num_bootstrap_samples,
                                         x_tick_multiplier=5 if option=='no-subsample' else 1, y_tick_multiplier=5, y_unit='pm-0, %',
                                         title='Distribution Shift to ImageNet-Vid-Anchors', x_label=x_label, y_label='ImageNet-Vid-Robust', 
                                         figsize=(12, 8), include_legend=False, return_separate_legend=False)
   
    os.makedirs(output_file_dir, exist_ok=True)

    filename = 'vid_robust_benign'
    if option == 'only-standard':
        filename += '_standard'
    if option == 'no-subsample':
        filename += '_subsample'
    if option == 'show-yx':
        filename += '_yx'
    fig.savefig(join(output_file_dir, f'{filename}.pdf'), dpi='figure', bbox_inches='tight', pad_inches=0.1)
    print(f"Plot saved to {join(output_file_dir, f'{filename}.pdf')}")


def prepare_df_for_plotting(df, df_metadata, columns, option):
    assert set(columns).issubset(set(df.columns))

    df = df[columns]
    df_metadata = df_metadata[[x+'_dataset_size' for x in columns]]
    df = df.merge(df_metadata, right_index=True, left_index=True)
    df = df.dropna()

    df['model_type'] = df.apply(get_model_type, axis=1)
    df['show_in_plot'] = df.apply(show_in_plot, axis=1, args=(option,))
    df['use_for_line_fit'] = df.apply(use_for_line_fit, axis=1)

    return df


if __name__ == '__main__':
    generate_xy_plot()
