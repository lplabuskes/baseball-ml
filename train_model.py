import os
os.add_dll_directory(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.7\bin")
import tensorflow as tf
import keras_tuner as kt
import numpy as np
from sklearn.model_selection import train_test_split
from datetime import datetime

from acquire_data import DATASET_PATH, generate_numpy_dataset


BATCH_SIZE = 64
SHUFFLE_BUFFER = 150
N_FEATURES = 56

def prep_dataset(normalizer: tf.keras.layers.Normalization=None):
    if not os.path.exists(DATASET_PATH):
        generate_numpy_dataset(2003, 2023)

    with np.load(DATASET_PATH) as data:
        features = data["features"]
        results = data["results"]

    X_train, X_test, y_train, y_test = train_test_split(features, results, train_size=0.8, shuffle=True)
    X_train, X_valid, y_train, y_valid = train_test_split(X_train, y_train, train_size=0.8, shuffle=True)

    if normalizer is not None:
        normalizer.adapt(X_train)
        X_train = normalizer(X_train)
        X_valid = normalizer(X_valid)

    training_dataset = tf.data.Dataset.from_tensor_slices((X_train, y_train))  # For training the model
    validation_dataset = tf.data.Dataset.from_tensor_slices((X_valid, y_valid))  # For stopping our model overfitting
    testing_dataset = tf.data.Dataset.from_tensor_slices((X_test, y_test))  # To evaluate at the very end

    training_dataset = training_dataset.shuffle(SHUFFLE_BUFFER).batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
    validation_dataset = validation_dataset.batch(BATCH_SIZE)
    testing_dataset = testing_dataset.batch(BATCH_SIZE)

    return training_dataset, validation_dataset, testing_dataset

def generate_model(hp: kt.HyperParameters):
    n_neurons = hp.Int("n_neurons", min_value=16, max_value=128, step=16)
    n_layers = hp.Int("n_layers", min_value=1, max_value=10)
    model = tf.keras.Sequential([
        tf.keras.layers.InputLayer(input_shape=(N_FEATURES,))
    ]+[
        tf.keras.layers.Dense(n_neurons, activation="selu", kernel_initializer="lecun_normal") for _ in range(n_layers)
    ]+[
        tf.keras.layers.Dense(1, activation="sigmoid")
    ])
    optimizer = tf.keras.optimizers.SGD(learning_rate=1e-3, momentum=0.9, nesterov=True)
    model.compile(loss=tf.keras.losses.binary_crossentropy, optimizer=optimizer, metrics=["mean_squared_error"])
    return model

def baseline_mse(dataset: tf.data.Dataset) -> float:
    count = 0
    sum = 0
    for _, res in dataset:
        sqdiff = tf.math.squared_difference(tf.cast(res, dtype=tf.float32), 0.54)
        count += sqdiff.shape[0]
        sum += tf.reduce_sum(sqdiff).numpy()
    return sum/count

if __name__ == "__main__":
    using_gpu = len(tf.config.list_physical_devices('GPU')) > 0
    assert(using_gpu)

    norm_layer = tf.keras.layers.Normalization(input_shape=(N_FEATURES,))
    training_dataset, validation_dataset, testing_dataset = prep_dataset(normalizer=norm_layer)

    tuner = kt.BayesianOptimization(generate_model, objective="val_loss", max_trials=20,
                                    overwrite=True, directory="models/tuner", project_name="baseball_ml")
    tuner.search(training_dataset, epochs=10, validation_data=validation_dataset)
    
    best_params = tuner.get_best_hyperparameters()[0]
    model = generate_model(best_params)

    lr_scheduler = tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5)
    early_stopping = tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True)

    history = model.fit(training_dataset, epochs=200, validation_data=validation_dataset,
                        callbacks=[lr_scheduler, early_stopping])

    final_model = tf.keras.Sequential([norm_layer, model])
    final_model.compile(loss=tf.keras.losses.binary_crossentropy, optimizer="sgd", metrics=["mean_squared_error"])
    bce_test, mse_test = final_model.evaluate(testing_dataset)
    mse_baseline = baseline_mse(testing_dataset)
    print(f"cross-entropy: {bce_test}, mse: {mse_test}, skill: {1-mse_test/mse_baseline}")
    datestring = datetime.now()
    model_path = datestring.strftime(".\\models\\%Y-%m-%d_%H-%M-%S.keras")
    final_model.save(model_path)