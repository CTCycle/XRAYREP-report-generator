import os
import sys
import pandas as pd
import tensorflow as tf
from keras.utils import plot_model

# set warnings
#------------------------------------------------------------------------------
import warnings
warnings.simplefilter(action='ignore', category = Warning)

# add modules path to sys
#------------------------------------------------------------------------------
if __name__ == '__main__':
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))  

# import modules and classes
#------------------------------------------------------------------------------    
from modules.components.data_assets import PreProcessing
from modules.components.model_assets import ModelTraining, RealTimeHistory, DataGenerator, XREPCaptioningModel
import modules.global_variables as GlobVar
import configurations as cnf

# [PREPROCESS DATA AND INITIALIZE TRINING DEVICE]
#==============================================================================
# Load the preprocessing module and then load saved preprocessed data from csv 
#==============================================================================

# load preprocessing module
#------------------------------------------------------------------------------
import modules.data_preprocessing

# load preprocessed csv files (train and test datasets)
#------------------------------------------------------------------------------
file_loc = os.path.join(GlobVar.model_savepath, 'preprocessing', 'XREP_train.csv') 
df_train = pd.read_csv(file_loc, encoding = 'utf-8', sep = (';' or ',' or ' ' or  ':'), low_memory=False)
file_loc = os.path.join(GlobVar.model_savepath, 'preprocessing', 'XREP_test.csv') 
df_test = pd.read_csv(file_loc, encoding = 'utf-8', sep = (';' or ',' or ' ' or  ':'), low_memory=False)

# [CREATE DATA GENERATOR]
#==============================================================================
# initialize a custom generator to load data on the fly
#==============================================================================

# initialize training device
#------------------------------------------------------------------------------
preprocessor = PreProcessing()
trainer = ModelTraining(device=cnf.training_device, seed=cnf.seed)

# load tokenizer to get padding length and vocabulary size
#------------------------------------------------------------------------------
tokenizer_path = os.path.join(GlobVar.model_savepath, 'preprocessing')
tokenizer = preprocessor.load_tokenizer(tokenizer_path, 'word_tokenizer')
vocab_size = len(tokenizer.word_index) + 1

# initialize generators for X and Y subsets
#------------------------------------------------------------------------------
train_datagen = DataGenerator(df_train, cnf.batch_size, cnf.picture_shape, 
                              shuffle=True, augmentation=cnf.augmentation)
test_datagen = DataGenerator(df_test, cnf.batch_size, cnf.picture_shape, 
                             shuffle=True, augmentation=cnf.augmentation)

# define the output signature of the generator using tf.TensorSpec, in order to
# successfully build a tf.dataset object from the custom generator
#------------------------------------------------------------------------------
x_batch, y_batch = train_datagen.__getitem__(0)
img_shape = x_batch[0].shape
tokenseq_shape = x_batch[1].shape
caption_shape = y_batch.shape
output_signature = ((tf.TensorSpec(shape=img_shape, dtype=tf.float32),
                     tf.TensorSpec(shape=tokenseq_shape, dtype=tf.float32)),
                     tf.TensorSpec(shape=caption_shape, dtype=tf.float32))

# generate tf.dataset from the initialized generator using the output signaturs.
# set prefetch (auto-tune) on the freshly created tf.dataset
#------------------------------------------------------------------------------
df_train = tf.data.Dataset.from_generator(lambda : train_datagen, output_signature=output_signature)
df_test = tf.data.Dataset.from_generator(lambda : test_datagen, output_signature=output_signature)
df_train = df_train.prefetch(buffer_size=tf.data.AUTOTUNE)
df_test = df_test.prefetch(buffer_size=tf.data.AUTOTUNE)

# [BUILD XREPORT MODEL]
#==============================================================================
# ....
#==============================================================================

# Print report with info about the training parameters
#------------------------------------------------------------------------------
print(f'''
-------------------------------------------------------------------------------
XRAYREP training report
-------------------------------------------------------------------------------
Number of train samples: {cnf.num_train_samples}
Number of test samples:  {cnf.num_test_samples}
-------------------------------------------------------------------------------
Batch size:              {cnf.batch_size}
Epochs:                  {cnf.epochs}
Vocabulary size:         {vocab_size + 1}
Caption length:          {caption_shape[1]} 
-------------------------------------------------------------------------------
''')

# initialize and compile the captioning model
#------------------------------------------------------------------------------
caption_model = XREPCaptioningModel(cnf.picture_shape, caption_shape[1], vocab_size, 
                                    cnf.embedding_dims, cnf.kernel_size, cnf.num_heads,
                                    cnf.learning_rate, cnf.XLA_acceleration, cnf.seed)

caption_model.compile()

# invoke call method to build a showcase model (in order to show summary and plot)
#------------------------------------------------------------------------------
showcase_model = caption_model.get_model()
showcase_model.summary()

# generate graphviz plot fo the model layout
#------------------------------------------------------------------------------
if cnf.generate_model_graph == True:
    plot_path = os.path.join(GlobVar.model_savepath, 'XREP_scheme.png')       
    plot_model(showcase_model, to_file = plot_path, show_shapes = True, 
               show_layer_names = True, show_layer_activations = True, 
               expand_nested = True, rankdir='TB', dpi = 400)    
    
# [TRAIN XREPORT MODEL]
#==============================================================================
# Setting callbacks and training routine for the XRAY captioning model. 
# to visualize tensorboard report, use command prompt on the model folder and 
# upon activating environment, use the bash command: 
#python -m tensorboard.main --logdir tensorboard/
#==============================================================================

# initialize real time plot callback 
#------------------------------------------------------------------------------
RTH_callback = RealTimeHistory(GlobVar.model_savepath, validation=True)

# initialize tensorboard
#------------------------------------------------------------------------------
if cnf.use_tensorboard == True:
    log_path = os.path.join(GlobVar.model_savepath, 'tensorboard')
    tensorboard_callback = tf.keras.callbacks.TensorBoard(log_dir=log_path, histogram_freq=1)
    callbacks = [RTH_callback, tensorboard_callback]    
else:    
    callbacks = [RTH_callback]

# define and execute training loop, then save the model weights at end
#------------------------------------------------------------------------------
training = caption_model.fit(df_train, validation_data=df_test, epochs=cnf.epochs, 
                             callbacks=callbacks, workers=6, use_multiprocessing=True) 

trainer.save_model(caption_model, GlobVar.model_savepath)



