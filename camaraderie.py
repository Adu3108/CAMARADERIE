import torch
from sklearn.svm import SVC
import numpy as np

from DCSAE_Encoder import DCSAE_Encoder
from train import DCSAE_Trainer

class CAMARADERIE:
    def __init__(self, encoder, decoder, n_latent, alpha, beta, gamma, rho, train_dataset, val_dataset, test_dataset):
        super(CAMARADERIE, self).__init__()
        self.n_latent = n_latent
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.rho = rho

        self.encoder = encoder
        self.decoder = decoder

        self.train_dataset = train_dataset
        self.val_dataset = val_dataset
        self.test_dataset = test_dataset

        self.encoder_weights_path = "./enc_only_weights.pt"
        self.weights_path = "./weights.pt"
        self.hyperparameters_path = "./hyperparameters.pt"

    def train(self):
        self.trainer = DCSAE_Trainer(self.n_latent, self.alpha, self.beta, self.beta, self.rho, self.encoder, self.decoder, self.train_dataset, self.val_dataset, self.weights_path, self.hyperparameters_path)
        self.trainer.train()
        self.ClientA_features, self.ClientA_Class = self.trainer.latent()

    def visualise(self):
        self.trainer.visualize()

    def convert(self):
        print(f'Converting model {self.weights_path} to encoder-only version...\n')
        full_model = torch.load(self.weights_path) # Load the weights stored in the .pt file
        self.hyperparameters = torch.load(self.hyperparameters_path)

        # Creating an instance of Encoder-only Network
        self.encoder = DCSAE_Encoder(self.n_latent)

        # Extracting the encoder only portion of the VAE Network
        encoder_dict = self.encoder.state_dict()
        for key in encoder_dict:
            encoder_dict[key] = full_model[key]

        # Saving the weights of the Encoder network in another .pt file
        torch.save(encoder_dict, self.encoder_weights_path)
        print("Conversion to Encoder-only Network complete")

    def extract(self):
        print(f'Starting feature extraction for input size {self.hyperparameters["input_d"]}')
        print(f'n_latent={self.hyperparameters["n_latent"]}')
        print(f'Using data set {self.test_dataset}')

        result = self.encoder.testing(self.test_dataset, self.encoder_weights_path)
        self.ClientB_class = result['final_class']

        self.ClientB_features = []
        for i in range(len(result["final_negative_mean"])):
            eps = torch.randn_like(result["final_negative_var"][i])
            mean_cpu = result["final_negative_mean"][i].cpu().detach().numpy()
            variance_cpu = result["final_negative_var"][i].cpu().detach().numpy()
            eps = eps.cpu().detach().numpy()
            z = mean_cpu + variance_cpu * eps
            self.ClientB_features.append(z)
        print("Feature extraction complete")

    def classify(self):
        ClientA_Z_tensor = torch.squeeze(torch.tensor(self.ClientA_features))
        ClientA_Z_numpy = ClientA_Z_tensor.cpu().detach().numpy()

        ClientB_Z_tensor = torch.squeeze(torch.tensor(self.ClientB_features))
        ClientB_Z_numpy = ClientB_Z_tensor.cpu().detach().numpy()

        classifier = SVC(gamma='auto', kernel='poly')
        classifier.fit(ClientA_Z_numpy, self.class_list)

        result = classifier.predict(ClientB_Z_numpy)

        actual_negative_instances = self.ClientB_class.count(0)
        actual_positive_instances = self.ClientB_class.count(1)

        negative_predictions = list(np.where(result == 0)[0])
        positive_predictions = list(np.where(result == 1)[0])

        total_positive_prediction = len(positive_predictions)
        total_negative_prediction = len(negative_predictions)

        true_positive_class = [self.ClientB_class[int(i)] for i in positive_predictions]
        true_negative_class = [self.ClientB_class[int(i)] for i in negative_predictions]

        predicted_negative_instances = true_negative_class.count(0)
        predicted_positive_instances = true_positive_class.count(1)

        print(f"Number of images belonging to positive class in the test dataset is {actual_positive_instances}")
        print(f"Number of predictions belonging to positive class is {total_positive_prediction}")
        print(f"Out of all the predictions made by the model, number of predictions that are correct for the positive class is {predicted_positive_instances}")
        print()
        print(f"Number of images belonging to negative class in the test dataset is {actual_negative_instances}")
        print(f"Number of predictions belonging to negative class is {total_negative_prediction}")
        print(f"Out of all the predictions made by the model, number of predictions that are correct for the negative class is {predicted_negative_instances}")