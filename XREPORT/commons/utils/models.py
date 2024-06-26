import os
import re
import numpy as np
import json
import tensorflow as tf
from tensorflow import keras
from keras import backend as K
from keras.models import Model
from keras import layers
from datetime import datetime



def save_model_parameters(parameters_dict, savepath):

    '''
    Saves the model parameters to a JSON file. The parameters are provided 
    as a dictionary and are written to a file named 'model_parameters.json' 
    in the specified directory.

    Keyword arguments:
        parameters_dict (dict): A dictionary containing the parameters to be saved.
        savepath (str): The directory path where the parameters will be saved.

    Returns:
        None       

    '''
    path = os.path.join(savepath, 'model_parameters.json')      
    with open(path, 'w') as f:
        json.dump(parameters_dict, f)

    
# function to create a folder where to save model checkpoints
#------------------------------------------------------------------------------
def model_savefolder(path, model_name):

    '''
    Creates a folder with the current date and time to save the model.
    
    Keyword arguments:
        path (str):       A string containing the path where the folder will be created.
        model_name (str): A string containing the name of the model.
    
    Returns:
        str: A string containing the path of the folder where the model will be saved.
        
    '''        
    today_datetime = str(datetime.now())
    truncated_datetime = today_datetime[:-10]
    today_datetime = truncated_datetime.replace(':', '').replace('-', '').replace(' ', 'H') 
    folder_name = f'{model_name}_{today_datetime}'
    model_folder_path = os.path.join(path, folder_name)
    if not os.path.exists(model_folder_path):
        os.mkdir(model_folder_path) 
                    
    return model_folder_path, folder_name

           
# [LEARNING RATE SCHEDULER]
#==============================================================================
@keras.utils.register_keras_serializable(package='LRScheduler')
class LRScheduler(keras.optimizers.schedules.LearningRateSchedule):
    def __init__(self, post_warmup_lr, warmup_steps):
        super().__init__()
        self.post_warmup_lr = post_warmup_lr
        self.warmup_steps = warmup_steps

    # implement encoder through call method  
    #--------------------------------------------------------------------------
    def __call__(self, step):
        global_step = tf.cast(step, tf.float32)
        warmup_steps = tf.cast(self.warmup_steps, tf.float32)
        warmup_progress = global_step/warmup_steps
        warmup_learning_rate = self.post_warmup_lr * warmup_progress

        return tf.cond(global_step < warmup_steps, lambda: warmup_learning_rate,
                       lambda: self.post_warmup_lr)
    
    # custom configurations
    #--------------------------------------------------------------------------
    def get_config(self):
        config = super(LRScheduler, self).get_config()
        config.update({'post_warmup_lr': self.post_warmup_lr,
                       'warmup_steps': self.warmup_steps})
        return config        
    
    # deserialization method 
    #--------------------------------------------------------------------------
    @classmethod
    def from_config(cls, config):
        return cls(**config)
    
      
# [IMAGE ENCODER MODEL]
#==============================================================================  
@keras.utils.register_keras_serializable(package='Encoders', name='ImageEncoder')
class ImageEncoder(keras.layers.Layer):
    def __init__(self, kernel_size, seed, **kwargs):
        super(ImageEncoder, self).__init__(**kwargs)
        self.kernel_size = kernel_size
        self.seed = seed
        self.conv1 = layers.Conv2D(128, kernel_size, strides=1, padding='same', 
                            activation='relu', kernel_initializer='he_uniform')        
        self.conv2 = layers.Conv2D(256, kernel_size, strides=1, padding='same', 
                            activation='relu', kernel_initializer='he_uniform')        
        self.conv3 = layers.Conv2D(256, kernel_size, strides=1, padding='same', 
                            activation='relu', kernel_initializer='he_uniform')  
        self.conv4 = layers.Conv2D(512, kernel_size, strides=1, padding='same', 
                            activation='relu', kernel_initializer='he_uniform')        
        self.conv5 = layers.Conv2D(512, kernel_size, strides=1, padding='same', 
                            activation='relu', kernel_initializer='he_uniform') 
        self.conv6 = layers.Conv2D(512, kernel_size, strides=1, padding='same', 
                            activation='relu', kernel_initializer='he_uniform')        
        self.maxpool1 = layers.MaxPooling2D((2, 2), strides=2, padding='same')
        self.maxpool2 = layers.MaxPooling2D((2, 2), strides=2, padding='same')
        self.maxpool3 = layers.MaxPooling2D((2, 2), strides=2, padding='same')
        self.maxpool4 = layers.MaxPooling2D((2, 2), strides=2, padding='same')          
        self.dense1 = layers.Dense(512, activation='relu', kernel_initializer='he_uniform')
        self.dense2 = layers.Dense(512, activation='relu', kernel_initializer='he_uniform')
        self.dense3 = layers.Dense(256, activation='relu', kernel_initializer='he_uniform')
        self.reshape = layers.Reshape((-1, 256))        

    # implement encoder through call method  
    #--------------------------------------------------------------------------
    def call(self, x, training=True):              
        layer = self.conv1(x)                  
        layer = self.maxpool1(layer) 
        layer = self.conv2(layer)                     
        layer = self.maxpool2(layer)        
        layer = self.conv3(layer)  
        layer = self.conv4(layer)                        
        layer = self.maxpool3(layer)                
        layer = self.conv5(layer) 
        layer = self.conv6(layer)               
        layer = self.maxpool4(layer)         
        layer = self.dense1(layer)        
        layer = self.dense2(layer)       
        layer = self.dense3(layer)       
        output = self.reshape(layer)              
        
        return output
    
    # serialize layer for saving  
    #--------------------------------------------------------------------------
    def get_config(self):
        config = super(ImageEncoder, self).get_config()       
        config.update({'kernel_size': self.kernel_size,
                       'seed' : self.seed})
        return config

    # deserialization method 
    #--------------------------------------------------------------------------
    @classmethod
    def from_config(cls, config):
        return cls(**config)
    

# [POSITIONAL EMBEDDING]
#==============================================================================
@keras.utils.register_keras_serializable(package='CustomLayers', name='PositionalEmbedding')
class PositionalEmbedding(keras.layers.Layer):
    def __init__(self, sequence_length, vocab_size, embedding_dims, mask_zero=True, **kwargs):
        super(PositionalEmbedding, self).__init__(**kwargs)
        self.sequence_length = sequence_length
        self.vocab_size = vocab_size 
        self.embedding_dim = embedding_dims        
        self.mask_zero = mask_zero        
        self.token_embeddings = layers.Embedding(input_dim=vocab_size, output_dim=embedding_dims)                        
        self.position_embeddings = layers.Embedding(input_dim=sequence_length, output_dim=embedding_dims)        
        self.embedding_scale = tf.math.sqrt(tf.cast(embedding_dims, tf.float32))        
    
    # implement positional embedding through call method  
    #--------------------------------------------------------------------------
    def call(self, inputs):
        length = tf.shape(inputs)[-1]
        positions = tf.range(start=0, limit=length, delta=1) 
        positions = tf.cast(positions, dtype=inputs.dtype)       
        embedded_tokens = self.token_embeddings(inputs)  
        embedded_tokens = embedded_tokens * self.embedding_scale
        embedded_positions = self.position_embeddings(positions)
        full_embedding = embedded_tokens + embedded_positions        
        if self.mask_zero==True:
            mask = tf.math.not_equal(inputs, 0)
            mask = tf.expand_dims(tf.cast(mask, tf.float32), axis=-1)                              
            full_embedding = full_embedding * mask            

        return full_embedding
    
    # compute the mask for padded sequences  
    #--------------------------------------------------------------------------
    def compute_mask(self, inputs, mask=None):
        return tf.math.not_equal(inputs, 0)
    
    # serialize layer for saving  
    #--------------------------------------------------------------------------
    def get_config(self):
        config = super(PositionalEmbedding, self).get_config()
        config.update({'sequence_length': self.sequence_length,
                       'vocab_size': self.vocab_size,
                       'embedding_dims': self.embedding_dim,
                       'bio_path' : self.bio_path,
                       'mask_zero': self.mask_zero})
        return config

    # deserialization method 
    #--------------------------------------------------------------------------
    @classmethod
    def from_config(cls, config):
        return cls(**config)
    

# [TRANSFORMER ENCODER]
#==============================================================================
@keras.utils.register_keras_serializable(package='Encoders', name='TransformerEncoderBlock')
class TransformerEncoderBlock(keras.layers.Layer):
    def __init__(self, embedding_dims, num_heads, seed, **kwargs):
        super(TransformerEncoderBlock, self).__init__(**kwargs)
        self.embedding_dims = embedding_dims       
        self.num_heads = num_heads  
        self.seed = seed       
        self.attention = layers.MultiHeadAttention(num_heads=num_heads, key_dim=self.embedding_dims)
        self.layernorm1 = layers.LayerNormalization()
        self.layernorm2 = layers.LayerNormalization()
        self.dense1 = layers.Dense(512, activation='relu', kernel_initializer='he_uniform')
        self.dense2 = layers.Dense(512, activation='relu', kernel_initializer='he_uniform')
        self.dense3 = layers.Dense(256, activation='relu', kernel_initializer='he_uniform')
        self.dense4 = layers.Dense(256, activation='relu', kernel_initializer='he_uniform')
        self.dropout1 = layers.Dropout(0.2, seed=seed)
        self.dropout2 = layers.Dropout(0.3, seed=seed)

    # implement transformer encoder through call method  
    #--------------------------------------------------------------------------
    def call(self, inputs, training=True):        
        inputs = self.layernorm1(inputs)
        inputs = self.dense1(inputs)
        inputs = self.dropout1(inputs)  
        inputs = self.dense2(inputs)            
        attention_output = self.attention(query=inputs, value=inputs, key=inputs,
                                          attention_mask=None, training=training)        
        layernorm = self.layernorm2(inputs + attention_output)
        layer = self.dense3(layernorm)
        layer = self.dropout2(layer)
        output = self.dense4(layer)        

        return output
    
    # serialize layer for saving  
    #--------------------------------------------------------------------------
    def get_config(self):
        config = super(TransformerEncoderBlock, self).get_config()
        config.update({'embedding_dims': self.embedding_dims,
                       'num_heads': self.num_heads,
                       'seed': self.seed})
        return config

    # deserialization method 
    #--------------------------------------------------------------------------
    @classmethod
    def from_config(cls, config):
        return cls(**config)
    

# [TRANSFORMER DECODER]
#==============================================================================
@keras.utils.register_keras_serializable(package='Decoders', name='TransformerDecoderBlock')
class TransformerDecoderBlock(keras.layers.Layer):
    def __init__(self, sequence_length, vocab_size, embedding_dims, num_heads, seed, **kwargs):
        super(TransformerDecoderBlock, self).__init__(**kwargs)
        self.sequence_length = sequence_length
        self.vocab_size = vocab_size
        self.embedding_dims = embedding_dims              
        self.num_heads = num_heads
        self.seed = seed        
        self.posembedding = PositionalEmbedding(sequence_length, vocab_size, embedding_dims, mask_zero=True)          
        self.MHA_1 = layers.MultiHeadAttention(num_heads=num_heads, key_dim=self.embedding_dims, dropout=0.2)
        self.MHA_2 = layers.MultiHeadAttention(num_heads=num_heads, key_dim=self.embedding_dims, dropout=0.2)
        self.FFN_1 = layers.Dense(512, activation='relu', kernel_initializer='he_uniform')
        self.FFN_2 = layers.Dense(self.embedding_dims, activation='relu', kernel_initializer='he_uniform')
        self.layernorm1 = layers.LayerNormalization()
        self.layernorm2 = layers.LayerNormalization()
        self.layernorm3 = layers.LayerNormalization()
        self.dense = layers.Dense(512, activation='relu', kernel_initializer='he_uniform')         
        self.outmax = layers.Dense(self.vocab_size, activation='softmax')
        self.dropout1 = layers.Dropout(0.2, seed=seed)
        self.dropout2 = layers.Dropout(0.3, seed=seed) 
        self.dropout3 = layers.Dropout(0.3, seed=seed)
        self.supports_masking = True 

    # implement transformer decoder through call method  
    #--------------------------------------------------------------------------
    def call(self, inputs, encoder_outputs, training=True, mask=None):
        inputs = tf.cast(inputs, tf.int32)
        inputs = self.posembedding(inputs)
        causal_mask = self.get_causal_attention_mask(inputs)        
        padding_mask = None
        combined_mask = None
        if mask is not None:
            padding_mask = tf.cast(mask[:, :, tf.newaxis], dtype=tf.int32)
            combined_mask = tf.cast(mask[:, tf.newaxis, :], dtype=tf.int32)
            combined_mask = tf.minimum(combined_mask, causal_mask)           
        attention_output1 = self.MHA_1(query=inputs, value=inputs, key=inputs,
                                       attention_mask=combined_mask, training=training)
        output1 = self.layernorm1(inputs + attention_output1)                       
        attention_output2 = self.MHA_2(query=output1, value=encoder_outputs,
                                       key=encoder_outputs, attention_mask=padding_mask,
                                       training=training)
        output2 = self.layernorm2(output1 + attention_output2)
        ffn_out = self.FFN_1(output2)
        ffn_out = self.dropout1(ffn_out, training=training)
        ffn_out = self.FFN_2(ffn_out)
        ffn_out = self.layernorm3(ffn_out + output2, training=training)
        ffn_out = self.dropout2(ffn_out, training=training)         
        ffn_out = self.dense(ffn_out)   
        ffn_out = self.dropout3(ffn_out, training=training)     
        preds = self.outmax(ffn_out)

        return preds

    # generate causal attention mask   
    #--------------------------------------------------------------------------
    def get_causal_attention_mask(self, inputs):
        input_shape = tf.shape(inputs)
        batch_size, sequence_length = input_shape[0], input_shape[1]
        i = tf.range(sequence_length)[:, tf.newaxis]
        j = tf.range(sequence_length)
        mask = tf.cast(i >= j, dtype='int32')
        mask = tf.reshape(mask, (1, input_shape[1], input_shape[1]))
        mult = tf.concat([tf.expand_dims(batch_size, -1), tf.constant([1, 1], dtype=tf.int32)],
                          axis=0)
        
        return tf.tile(mask, mult) 
    
    # serialize layer for saving  
    #--------------------------------------------------------------------------
    def get_config(self):
        config = super(TransformerDecoderBlock, self).get_config()
        config.update({'sequence_length': self.sequence_length,
                       'vocab_size': self.vocab_size,
                       'embedding_dims': self.embedding_dims,                       
                       'num_heads': self.num_heads,
                       'seed': self.seed})
        return config

    # deserialization method 
    #--------------------------------------------------------------------------
    @classmethod
    def from_config(cls, config):
        return cls(**config)
     

# [XREP CAPTIONING MODEL]
#==============================================================================
@keras.utils.register_keras_serializable(package='Models', name='XREPCaptioningModel')
class XREPCaptioningModel(keras.Model):    
    def __init__(self, picture_shape, sequence_length, vocab_size, embedding_dims, kernel_size,
                 num_heads, learning_rate, XLA_state, seed=42, **kwargs):   
        super(XREPCaptioningModel, self).__init__(**kwargs)
        self.loss_tracker = keras.metrics.Mean(name='loss')
        self.acc_tracker = keras.metrics.Mean(name='accuracy')
        self.picture_shape = picture_shape
        self.sequence_length = sequence_length
        self.vocab_size = vocab_size 
        self.embedding_dims = embedding_dims       
        self.kernel_size = kernel_size
        self.num_heads = num_heads
        self.learning_rate = learning_rate
        self.XLA_state = XLA_state                
        self.seed = seed                         
        self.image_encoder = ImageEncoder(kernel_size, seed)        
        self.encoders = [TransformerEncoderBlock(embedding_dims, num_heads, seed) for i in range(3)]        
        self.decoder = TransformerDecoderBlock(sequence_length, self.vocab_size, embedding_dims, 
                                                 num_heads, seed) 
    # calculate loss
    #--------------------------------------------------------------------------
    def calculate_loss(self, y_true, y_pred, mask):               
        loss = self.loss(y_true, y_pred)
        mask = tf.cast(mask, dtype=loss.dtype)
        loss *= mask
        return tf.reduce_sum(loss)/(tf.reduce_sum(mask) + keras.backend.epsilon())
    
    # calculate accuracy
    #--------------------------------------------------------------------------
    def calculate_accuracy(self, y_true, y_pred, mask): 
        y_true = tf.cast(y_true, dtype=tf.float32)
        y_pred_argmax = tf.cast(tf.argmax(y_pred, axis=2), dtype=tf.float32)
        accuracy = tf.equal(y_true, y_pred_argmax)
        accuracy = tf.math.logical_and(mask, accuracy)
        accuracy = tf.cast(accuracy, dtype=tf.float32)
        mask = tf.cast(mask, dtype=tf.float32)

        return tf.reduce_sum(accuracy)/(tf.reduce_sum(mask) + keras.backend.epsilon())

    # calculate the caption loss and accuracy
    #--------------------------------------------------------------------------
    def _compute_caption_loss_and_acc(self, img_embed, batch_seq, training=True):        
        batch_seq_inp = batch_seq[:, :-1]
        batch_seq_true = batch_seq[:, 1:]
        mask = tf.math.not_equal(batch_seq_true, 0)
        encoder_out = img_embed        
        for encoder in self.encoders:
            encoder_out = encoder(encoder_out, training=training) 
        batch_seq_pred = self.decoder(batch_seq_inp, encoder_out, training=training, mask=mask)
        loss = self.calculate_loss(batch_seq_true, batch_seq_pred, mask)
        acc = self.calculate_accuracy(batch_seq_true, batch_seq_pred, mask)

        return loss, acc
    
    # define train step
    #--------------------------------------------------------------------------
    def train_step(self, batch_data):
        x_data, y_data = batch_data
        batch_img, batch_seq = x_data        
        img_embed = self.image_encoder(batch_img)       
        with tf.GradientTape() as tape:
            loss, acc = self._compute_caption_loss_and_acc(img_embed, batch_seq, training=True) 
        encoder_vars = [var for encoder in self.encoders for var in encoder.trainable_variables]   
        train_vars = encoder_vars + self.decoder.trainable_variables        
        grads = tape.gradient(loss, train_vars)
        self.optimizer.apply_gradients(zip(grads, train_vars))        
        self.loss_tracker.update_state(loss)
        self.acc_tracker.update_state(acc)              
        
        return {'loss': self.loss_tracker.result(),
                'acc': self.acc_tracker.result()}

    # define test step
    #--------------------------------------------------------------------------
    def test_step(self, batch_data):
        x_data, y_data = batch_data
        batch_img, batch_seq = x_data         
        img_embed = self.image_encoder(batch_img)        
        loss, acc = self._compute_caption_loss_and_acc(img_embed, batch_seq, training=False)         
        self.loss_tracker.update_state(loss)
        self.acc_tracker.update_state(acc)        

        return {'loss': self.loss_tracker.result(),
                'acc': self.acc_tracker.result()}        
 
    # implement captioning model through call method  
    #--------------------------------------------------------------------------    
    def call(self, inputs, training=True):

        images, sequences = inputs        
        mask = tf.math.not_equal(sequences, 0)             
        image_features = self.image_encoder(images) 
        encoder_out = image_features 
        batch_seq_pred = sequences       
        for encoder in self.encoders:
            encoder_out = encoder(encoder_out, training=training) 
        decoder_out = self.decoder(batch_seq_pred, encoder_out, training=training, mask=mask)        

        return decoder_out  
    
    # print summary
    #--------------------------------------------------------------------------
    def get_model(self):
        image_input = layers.Input(shape=self.picture_shape)    
        seq_input = layers.Input(shape=(self.sequence_length, ))
        model = Model(inputs=[image_input, seq_input], outputs = self.call([image_input, seq_input], 
                      training=False)) 
        
        return model       

    # compile the model
    #--------------------------------------------------------------------------
    def compile(self):
        lr_schedule = LRScheduler(self.learning_rate, warmup_steps=10)
        loss = keras.losses.SparseCategoricalCrossentropy(from_logits=False, 
                                                          reduction=keras.losses.Reduction.NONE)  
        metric = keras.metrics.SparseCategoricalAccuracy()  
        opt = keras.optimizers.Adam(learning_rate=lr_schedule)          
        super(XREPCaptioningModel, self).compile(optimizer=opt, loss=loss, metrics=metric, 
                                                 run_eagerly=False, jit_compile=self.XLA_state)   
        
    # track metrics and losses  
    #--------------------------------------------------------------------------
    @property
    def metrics(self):
        return [self.loss_tracker, self.acc_tracker]     
 
    # serialize layer for saving  
    #--------------------------------------------------------------------------
    def get_config(self):
        config = super(XREPCaptioningModel, self).get_config()
        config.update({'picture_shape': self.picture_shape,
                       'sequence_length': self.sequence_length,
                       'vocab_size': self.vocab_size,
                       'embedding_dims': self.embedding_dims,                       
                       'kernel_size': self.kernel_size,
                       'num_heads': self.num_heads,
                       'learning_rate' : self.learning_rate,
                       'XLA_state' : self.XLA_state,                 
                       'seed' : self.seed})
        return config

    # deserialization method 
    #--------------------------------------------------------------------------
    @classmethod
    def from_config(cls, config):
        return cls(**config)  
    

# [TOOLS FOR TRAINING MACHINE LEARNING MODELS]
#==============================================================================
class ModelTraining:    
       
    def __init__(self, seed=42):                            
        np.random.seed(seed)
        tf.random.set_seed(seed)         
        self.available_devices = tf.config.list_physical_devices()               
        print('The current devices are available:\n')        
        for dev in self.available_devices:            
            print(dev)

    # set device
    #--------------------------------------------------------------------------
    def set_device(self, device='default', use_mixed_precision=False):

        if device == 'GPU':
            self.physical_devices = tf.config.list_physical_devices('GPU')
            if not self.physical_devices:
                print('\nNo GPU found. Falling back to CPU\n')
                tf.config.set_visible_devices([], 'GPU')
            else:
                if use_mixed_precision == True:
                    policy = keras.mixed_precision.Policy('mixed_float16')
                    keras.mixed_precision.set_global_policy(policy) 
                tf.config.set_visible_devices(self.physical_devices[0], 'GPU')
                os.environ['TF_GPU_ALLOCATOR']='cuda_malloc_async'                 
                print('\nGPU is set as active device\n')
                   
        elif device == 'CPU':
            tf.config.set_visible_devices([], 'GPU')
            print('\nCPU is set as active device\n')    
    
    #--------------------------------------------------------------------------   
    def save_subclassed_model(self, model, path):

        '''
        Saves a subclassed Keras model's weights and configuration to the specified directory.

        Keyword Arguments:
            model (keras.Model): The model to save.
            path (str): Directory path for saving model weights and configuration.        

        Returns:
            None
        '''        
        weights_path = os.path.join(path, 'model_weights.h5')  
        model.save_weights(weights_path)        
        config = model.get_config()
        config_path = os.path.join(path, 'model_configuration.json')
        with open(config_path, 'w') as json_file:
            json.dump(config, json_file)
        config_path = os.path.join(path, 'model_architecture.json')
        with open(config_path, 'w') as json_file:
            json_file.write(model.to_json())             
    
    
# [TOOLKIT TO USE THE PRETRAINED MODEL]
#==============================================================================
class Inference:

    def __init__(self, seed):
        self.seed = seed
        np.random.seed(seed)
        tf.random.set_seed(seed)  
   
    #--------------------------------------------------------------------------
    def load_pretrained_model(self, path):

        '''
        Load pretrained keras model (in folders) from the specified directory. 
        If multiple model directories are found, the user is prompted to select one,
        while if only one model directory is found, that model is loaded directly.
        If `load_parameters` is True, the function also loads the model parameters 
        from the target .json file in the same directory. 

        Keyword arguments:
            path (str): The directory path where the pretrained models are stored.
            load_parameters (bool, optional): If True, the function also loads the 
                                              model parameters from a JSON file. 
                                              Default is True.

        Returns:
            model (keras.Model): The loaded Keras model.

        '''        
        model_folders = []
        for entry in os.scandir(path):
            if entry.is_dir():
                model_folders.append(entry.name)
        if len(model_folders) > 1:
            model_folders.sort()
            index_list = [idx + 1 for idx, item in enumerate(model_folders)]     
            print('Please select a pretrained model:') 
            print()
            for i, directory in enumerate(model_folders):
                print(f'{i + 1} - {directory}')        
            print()               
            while True:
                try:
                    dir_index = int(input('Type the model index to select it: '))
                    print()
                except:
                    continue
                break                         
            while dir_index not in index_list:
                try:
                    dir_index = int(input('Input is not valid! Try again: '))
                    print()
                except:
                    continue
            self.folder_path = os.path.join(path, model_folders[dir_index - 1])

        elif len(model_folders) == 1:
            self.folder_path = os.path.join(path, model_folders[0])                   
        
        # read model serialization configuration and initialize it           
        path = os.path.join(self.folder_path, 'model', 'model_configuration.json')
        with open(path, 'r') as f:
            configuration = json.load(f)        
        model = XREPCaptioningModel.from_config(configuration)             

        # set inputs to build the model 
        pic_shape = tuple(configuration['picture_shape'])
        sequence_length = configuration['sequence_length']
        build_inputs = (tf.constant(0.0, shape=(1, *pic_shape)),
                        tf.constant(0, shape=(1, sequence_length), dtype=tf.int32))
        model(build_inputs, training=False) 

        # load weights into the model 
        weights_path = os.path.join(self.folder_path, 'model', 'model_weights.h5')
        model.load_weights(weights_path)                       
        
        return model, configuration                  

    #--------------------------------------------------------------------------    
    def greed_search_generator(self, model, paths, picture_size, max_length, tokenizer):
        
        reports = {}
        vocabulary = tokenizer.get_vocab()
        start_token = '[CLS]'
        end_token = '[SEP]'        
        index_lookup = dict(zip(range(len(vocabulary)), vocabulary))        
        for pt in paths:
            print(f'\nGenerating report for images {os.path.basename(pt)}\n')
            image = tf.io.read_file(pt)
            image = tf.image.decode_image(image, channels=1)
            image = tf.image.resize(image, picture_size)            
            image = image/255.0 
            input_image = tf.expand_dims(image, 0)
            features = model.image_encoder(input_image)           
            encoded_img = model.layers[1](features, training=False)   
            encoded_img = model.layers[2](encoded_img, training=False)  
            encoded_img = model.layers[3](encoded_img, training=False)  

            # teacher forging method to generate tokens through the decoder
            decoded_caption = start_token              
            for i in range(max_length):                     
                tokenized_outputs = tokenizer(decoded_caption, add_special_tokens=False, return_tensors='tf',
                                              padding='max_length', max_length=max_length) 
                  
                tokenized_caption = tokenized_outputs['input_ids']                                                                                                        
                tokenized_caption = tf.constant(tokenized_caption, dtype=tf.int32)                                                      
                mask = tf.math.not_equal(tokenized_caption, 0)                                                
                predictions = model.decoder(tokenized_caption, encoded_img, training=False, mask=mask)                                                                                                                    
                sampled_token_index = np.argmax(predictions[0, i, :])                               
                sampled_token = index_lookup[sampled_token_index]                      
                if sampled_token == end_token: 
                      break                
                decoded_caption = decoded_caption + f' {sampled_token}'

            text = re.sub(r'##', '', decoded_caption)
            text = re.sub(r'\s+', ' ', text)           
            print(f'Predicted report for image: {os.path.basename(pt)}', text)          

        return reports
   

# [VALIDATION OF PRETRAINED MODELS]
#==============================================================================
class ModelValidation:


    # model weights check
    #-------------------------------------------------------------------------- 
    def model_weigths_check(self, unsaved_model, save_path):

        # read model serialization configuration and initialize it           
        path = os.path.join(save_path, 'model', 'model_configuration.json')
        with open(path, 'r') as f:
            configuration = json.load(f)        
        saved_model = XREPCaptioningModel.from_config(configuration)             

        # set inputs to build the model 
        pic_shape = tuple(configuration['picture_shape'])
        sequence_length = configuration['sequence_length']
        build_inputs = (tf.constant(0.0, shape=(1, *pic_shape)),
                        tf.constant(0, shape=(1, sequence_length), dtype=tf.int32))
        saved_model(build_inputs, training=False) 

        # load weights into the model 
        weights_path = os.path.join(save_path, 'model', 'model_weights.h5')
        saved_model.load_weights(weights_path)        

        if len(unsaved_model.layers) != len(saved_model.layers):
            print('Models do not have the same number of layers')
            return

        # Iterate through each layer
        for layer1, layer2 in zip(unsaved_model.layers, saved_model.layers):
        # Check if both layers have weights
            if layer1.get_weights() and layer2.get_weights():
                # Compare weights
                weights1 = layer1.get_weights()[0] 
                weights2 = layer2.get_weights()[0] 
                biases1 = layer1.get_weights()[1] if len(layer1.get_weights()) > 1 else None
                biases2 = layer2.get_weights()[1] if len(layer2.get_weights()) > 1 else None
                
                # Using numpy to check if weights and biases are identical
                if not (np.array_equal(weights1, weights2) and (biases1 is None or np.array_equal(biases1, biases2))):
                    print(f'Weights or biases do not match in layer {layer1.name}')
                else:
                    print(f'Layer {layer1.name} weights and biases are identical')
            else:
                print(f'Layer {layer1.name} does not have weights to compare')
            

    
    
