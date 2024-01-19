# Define general variables
#------------------------------------------------------------------------------
generate_model_graph = True
use_mixed_precision = True
use_tensorboard = False
XLA_acceleration = False

# Define variables for the training
#------------------------------------------------------------------------------
seed = 42
training_device = 'GPU'
epochs = 30
learning_rate = 0.001
batch_size = 100
embedding_dims = 256
kernel_size = 4
num_heads = 4

# define variables for data processing
#------------------------------------------------------------------------------
picture_size = (124, 124)
num_channels = 1
image_shape = picture_size + (num_channels,)
num_samples = 30000
test_size = 0.2
data_augmentation = False





