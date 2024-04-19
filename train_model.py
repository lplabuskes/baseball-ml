import os
os.add_dll_directory(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.7\bin")
import tensorflow as tf
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
    training_dataset = tf.data.Dataset.from_tensor_slices((X_train, y_train))  # For training the model
    validation_dataset = tf.data.Dataset.from_tensor_slices((X_valid, y_valid))  # For stopping our model overfitting
    testing_dataset = tf.data.Dataset.from_tensor_slices((X_test, y_test))  # To evaluate at the very end

    if normalizer is not None:
        normalizer.adapt(X_train)

    training_dataset = training_dataset.shuffle(SHUFFLE_BUFFER).batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
    validation_dataset = validation_dataset.batch(BATCH_SIZE)
    testing_dataset = testing_dataset.batch(BATCH_SIZE)

    return training_dataset, validation_dataset, testing_dataset

def generate_model(n_features: int, n_layers: int=4, n_neurons: int=100):
    norm_layer = tf.keras.layers.Normalization(input_shape=(n_features,))
    model = tf.keras.Sequential([
        norm_layer
    ]+[
        tf.keras.layers.Dense(n_neurons, activation="selu", kernel_initializer="lecun_normal") for _ in range(n_layers)
    ]+[
        tf.keras.layers.Dense(1, activation="sigmoid")
    ])
    optimizer = tf.keras.optimizers.SGD(learning_rate=1e-3, momentum=0.9, nesterov=True)
    model.compile(loss=tf.keras.losses.binary_crossentropy, optimizer=optimizer, metrics=["mean_squared_error"])
    return norm_layer, model

def baseline_mse(dataset: tf.data.Dataset) -> float:
    count = 0
    sum = 0
    for _, res in testing_dataset:
        sqdiff = tf.math.squared_difference(tf.cast(res, dtype=tf.float32), 0.54)
        count += sqdiff.shape[0]
        sum += tf.reduce_sum(sqdiff).numpy()
    return sum/count

if __name__ == "__main__":
    using_gpu = len(tf.config.list_physical_devices('GPU')) > 0
    assert(using_gpu)

    norm_layer, model = generate_model(n_features=N_FEATURES, n_layers=3, n_neurons=50)
    training_dataset, validation_dataset, testing_dataset = prep_dataset(normalizer=norm_layer)

    lr_scheduler = tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5)
    early_stopping = tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True)

    history = model.fit(training_dataset, epochs=200, validation_data=validation_dataset,
                        callbacks=[lr_scheduler, early_stopping])

    bce_test, mse_test = model.evaluate(testing_dataset)
    mse_baseline = baseline_mse(testing_dataset)
    print(f"cross-entropy: {bce_test}, mse: {mse_test}, skill: {1-mse_test/mse_baseline}")
    datestring = datetime.now()
    model_path = datestring.strftime(".\\models\\%Y-%m-%d_%H-%M-%S.keras")
    model.save(model_path)