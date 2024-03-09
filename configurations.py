# Advanced settings for training 
#------------------------------------------------------------------------------
use_mixed_precision = True
use_tensorboard = False
XLA_acceleration = False
training_device = 'GPU'
num_processors = 6

# Settings for training routine
#------------------------------------------------------------------------------
epochs = 20
learning_rate = 0.001
batch_size = 10

# Model settings
#------------------------------------------------------------------------------
picture_shape = (144, 144, 1)
embedding_dims = 768 # compatible with BioBERT embedding dimensions
kernel_size = 2
num_heads = 4
generate_model_graph = True

# Settings for training data 
#------------------------------------------------------------------------------
num_train_samples = 20000
num_test_samples = 2000
augmentation = False

# General settings 
#------------------------------------------------------------------------------
seed = 72
split_seed = 40






